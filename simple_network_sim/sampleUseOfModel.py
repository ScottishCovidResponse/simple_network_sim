import argparse
import copy
import logging
import logging.config
import random
import sys
import time
from datetime import datetime

from pathlib import Path
from typing import Optional

import matplotlib.pyplot as plt

from . import common, network_of_populations as ss, loaders

# Default logger, used if module not called as __main__
logger = logging.getLogger(__name__)


def main(argv):
    t0 = time.time()

    print(argv)
    args = build_args(argv)

    # Set up log config
    setup_logger(args)

    logger.info(
        "Parameters\n%s",
        "\n".join(f"\t{key}={value}" for key, value in args._get_kwargs()),
    )

    network = ss.createNetworkOfPopulation(
        disasesProgressionFn=args.compartment_transition,
        populationFn=args.population,
        graphFn=args.commutes,
        ageInfectionMatrixFn=args.mixing_matrix,
        movementMultipliersFn=args.movement_multipliers,
    )

    aggregated = None
    infections = {}
    if args.cmd == "seeded":
        with open(args.input) as fp:
            infections = loaders.readInitialInfections(fp)
    for _ in range(args.trials):
        disposableNetwork = copy.deepcopy(network)

        if args.cmd == "random":
            # If random, pick new infections at each iteration
            infections = {}
            for regionID in random.choices(
                list(disposableNetwork.graph.nodes()), k=args.regions
            ):
                infections[regionID] = {}
                for age in args.age_groups:
                    infections[regionID][age] = args.infected

        ss.exposeRegions(infections, disposableNetwork.states[0])

        ss.basicSimulationInternalAgeStructure(disposableNetwork, args.time)
        # index by all columns so it's we can safely aggregate
        indexed = ss.modelStatesToPandas(disposableNetwork.states).set_index(
            ["time", "healthboard", "age", "state"]
        )
        if aggregated is None:
            aggregated = indexed
        else:
            aggregated.total += indexed.total

    averaged = aggregated.reset_index()
    averaged.total /= args.trials

    filename = f"{args.output_prefix}-{int(time.time())}"

    averaged.to_csv(f"{filename}.csv", index=False)
    ss.plotStates(
        averaged, states=args.plot_states, healthboards=args.plot_healthboards
    ).savefig(f"{filename}.pdf", dpi=300)

    logger.info("Read the dataframe from: %s.csv", filename)
    logger.info("Open the visualisation from: %s.pdf", filename)
    logger.info("Took %.2fs to run the simulation.", time.time() - t0)


def setup_logger(args: Optional[argparse.Namespace] = None) -> None:
    """Configure package-level logger instance.
    
    :param args: argparse.Namespace
        args.logfile (pathlib.Path) is used to create a logfile if present
        args.verbose and args.debug control logging level to sys.stderr

    This function can be called without args, in which case it configures the
    package logger to write WARNING and above to STDERR.

    When called with args, it uses args.logfile to determine if logs (by
    deafult, INFO and above) should be written to a file, and the path of
    that file. args.verbose and args.debug are used to control reporting
    level.
    """
    # Dictionary to define logging configuration
    logconf = {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "standard": {
                "format": "[%(asctime)s] [%(name)s] [%(levelname)s] %(message)s",
            },
        },
        "handlers": {
            "stderr": {
                "level": "WARNING",
                "class": "logging.StreamHandler",
                "formatter": "standard",
                "stream": "ext://sys.stderr",
            },
        },
        "loggers": {__package__: {"handlers": ["stderr"], "level": "DEBUG",},},
    }

    # If args.logpath is specified, add logfile
    if args is not None and args.logfile is not None:
        logdir = args.logfile.parents[0]
        # If the logfile is going in another directory, we must
        # create/check if the directory is there
        try:
            if not logdir == Path.cwd():
                logdir.mkdir(exist_ok=True)
        except OSError:
            logger.error("Could not create %s for logging", logdir, exc_info=True)
            raise SystemExit(1)  # Substitute meaningful error code when known
        # Add logfile configuration
        logconf["handlers"]["logfile"] = {
            "class": "logging.FileHandler",
            "level": "INFO",
            "formatter": "standard",
            "filename": str(args.logfile),
            "encoding": "utf8",
        }
        logconf["loggers"][__package__]["handlers"].append("logfile")

    # Set STDERR/logfile levels if args.verbose/args.debug specified
    if args is not None and args.verbose:
        logconf["handlers"]["stderr"]["level"] = "INFO"
    elif args is not None and args.debug:
        logconf["handlers"]["stderr"]["level"] = "DEBUG"
        logconf["handlers"]["logfile"]["level"] = "DEBUG"

    # Configure logger
    logging.config.dictConfig(logconf)


def build_args(argv):
    """Return parsed CLI arguments as argparse.Namespace."""
    sampledir = Path(__file__).parents[1] / "sample_input_files"

    parser = argparse.ArgumentParser(
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
        description="Uses the deterministic network of populations model to simulation the disease progression",
    )
    parser.add_argument(
        "--compartment-transition",
        default=sampledir / "compartmentTransitionByAge.csv",
        help="Epidemiological rate parameters for movement within the compartmental model.",
    )
    parser.add_argument(
        "--population",
        default=sampledir / "sample_hb2019_pop_est_2018_row_based.csv",
        type=Path,
        help="This file contains age-and-sex-stratified population numbers by geographic unit.",
    )
    parser.add_argument(
        "--commutes",
        default=sampledir / "sample_scotHB_commute_moves_wu01.csv",
        type=Path,
        help="This contains origin-destination flow data during peacetime for health boards",
    )
    parser.add_argument(
        "--mixing-matrix",
        default=sampledir / "simplified_age_infection_matrix.csv",
        type=Path,
        help="This is a sample square matrix of mixing - each column and row header is an age category.",
    )
    parser.add_argument(
        "--movement-multipliers",
        help="By using this parameter you can adjust dampening or heightening people movement through time",
    )
    parser.add_argument(
        "--time",
        default=200,
        type=int,
        help="The number of time steps to take for each simulation",
    )
    parser.add_argument(
        "-l",
        "--logfile",
        dest="logfile",
        default=None,
        type=Path,
        help="Path for logging output",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        dest="verbose",
        action="store_true",
        help="Provide verbose output to STDERR",
    )
    parser.add_argument(
        "--debug", action="store_true", help="Provide debug output to STDERR"
    )
    parser.add_argument(
        "--plot-healthboards",
        default=None,
        nargs="+",
        help="If set, will only plot the specified healthboards",
    )
    parser.add_argument(
        "--plot-states",
        default=None,
        nargs="+",
        help="If set, will only plot the specified states",
    )

    sp = parser.add_subparsers(dest="cmd", required=True)

    # Parameters when using the random infection approach
    randomCmd = sp.add_parser(
        "random",
        help="Randomly pick regions to infect",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    randomCmd.add_argument("--regions", default=1, help="Number of regions to infect")
    randomCmd.add_argument(
        "--age-groups", nargs="+", default=["[17,70)"], help="Age groups to infect"
    )
    randomCmd.add_argument(
        "--trials", default=100, type=int, help="Number of experiments to run"
    )
    randomCmd.add_argument(
        "--infected",
        default=100,
        type=int,
        help="Number of infected people in each region/age group",
    )
    randomCmd.add_argument(
        "output_prefix",
        type=str,
        help="Prefix used when exporting the dataframe and plot",
    )

    # Parameters when using the seeded infection approach
    seededCmd = sp.add_parser(
        "seeded",
        help="Use a seed file with infected regions",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    seededCmd.add_argument(
        "--trials", default=1, type=int, help="Number of experiments to run"
    )
    seededCmd.add_argument(
        "input", type=Path, help="File name with the seed region seeds"
    )
    seededCmd.add_argument(
        "output_prefix",
        type=str,
        help="Prefix use when exporting the dataframe and plot",
    )

    return parser.parse_args(argv)


if __name__ == "__main__":
    # The logger name inherits from the package, if called as __main__
    logger = logging.getLogger(f"{__package__}.{__name__}")
    main(sys.argv[1:])
