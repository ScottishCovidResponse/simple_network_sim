"""
This is the main module used to run simulations based on network of populations
"""
# pylint: disable=import-error
import argparse
from concurrent import futures
from functools import reduce
import logging
import logging.config
from pathlib import Path
import sys
import time
from typing import Optional, List, NamedTuple

from data_pipeline_api import standard_api  # type: ignore
import numpy as np  # type: ignore
import pandas as pd  # type: ignore

from simple_network_sim.common import IssueSeverity, log_issue
from . import common, loaders
from . import network_of_populations as ss

# Default logger, used if module not called as __main__
logger = logging.getLogger(__name__)


def main(argv):
    """
    Main function to run the network of populations simulation
    """
    t0 = time.time()

    args = build_args(argv)
    setup_logger(args)
    logger.info("Parameters\n%s", "\n".join(f"\t{key}={value}" for key, value in args._get_kwargs()))  # pylint: disable=protected-access

    issues: List[standard_api.Issue] = []

    info = common.get_repo_info()
    if not info.git_sha:
        log_issue(
            logger,
            "Not running from a git repo, so no git_sha associated with the run",
            IssueSeverity.HIGH,
            issues,
        )
    elif info.is_dirty:
        log_issue(logger, "Running out of a dirty git repo", IssueSeverity.HIGH, issues)
    with standard_api.StandardAPI.from_config(args.data_pipeline_config, uri=info.uri, git_sha=info.git_sha) as store:
        network, new_issues = ss.createNetworkOfPopulation(
            store.read_table("human/compartment-transition", "compartment-transition"),
            store.read_table("human/population", "population"),
            store.read_table("human/commutes", "commutes"),
            store.read_table("human/mixing-matrix", "mixing-matrix"),
            store.read_table("human/infectious-compartments", "infectious-compartments"),
            store.read_table("human/infection-probability", "infection-probability"),
            store.read_table("human/initial-infections", "initial-infections"),
            store.read_table("human/trials", "trials"),
            store.read_table("human/start-end-date", "start-end-date"),
            store.read_table("human/movement-multipliers", "movement-multipliers") if args.use_movement_multipliers else None,
            store.read_table("human/stochastic-mode", "stochastic-mode"),
        )
        issues.extend(new_issues)

        random_seed = loaders.readRandomSeed(store.read_table("human/random-seed", "random-seed"))
        results = runSimulation(network, random_seed, issues=issues, max_workers=None if not args.workers else args.workers)
        aggregated = aggregateResults(results)

        logger.info("Writing output")
        store.write_table(
            "output/simple_network_sim/outbreak-timeseries",
            "outbreak-timeseries",
            aggregated.output,
            issues=issues,
            description=aggregated.description,
        )

        logger.info("Took %.2fs to run the simulation.", time.time() - t0)
        logger.info(
            "Use `python -m simple_network_sim.network_of_populations.visualisation -h` to find out how to take "
            "a peak what you just ran. You will need use the access-<hash>.yaml file that was created by this run."
        )


def runSimulation(
        network: ss.NetworkOfPopulation,
        random_seed: int,
        issues: List[standard_api.Issue],
        max_workers: Optional[int] = None,
) -> List[pd.DataFrame]:
    """Run pre-created network

    :param network: object representing the network of populations
    :param random_seed: seed to use when instantiating the SeedSequence object
    :param issues: list of issues to report to the pipeline
    :param max_workers: maximum number of processes to spawn when running multiple simulations
    :return: Result runs for all trials of the simulation
    """
    results = []
    with futures.ProcessPoolExecutor(max_workers=max_workers) as executor:
        delayed: List[futures.Future] = []
        for seq in np.random.SeedSequence(random_seed).spawn(network.trials):
            delayed.append(
                executor.submit(
                    ss.basicSimulationInternalAgeStructure,
                    network,
                    network.initialInfections,
                    np.random.default_rng(seq),
                )
            )

        for t, future in enumerate(futures.as_completed(delayed), start=1):
            logger.info("Running simulation (%s/%s)", t, network.trials)
            df, new_issues = future.result()
            issues.extend(new_issues)
            results.append(df)

    return results


class AggregatedResults(NamedTuple):
    """
    This object contains the results of a simulation and a small description
    """
    output: pd.DataFrame
    description: str = "A dataframe of the number of people in each node, compartment and age over time"


def aggregateResults(results: List[pd.DataFrame]) -> AggregatedResults:
    """Aggregate results from runs

    :param results: result runs from runSimulation
    :return: Averaged number of infection through time, for all trial
    """
    if len(results) == 1:
        aggregated = results[0]
    else:
        results = [result.set_index(["date", "node", "age", "state"]).total for result in results]
        average = reduce(lambda x, y: x.add(y), results) / len(results)

        aggregated = average.reset_index()
    # The data pipeline API doesn't support categorical data, so we need to convert these to strings
    return AggregatedResults(output=aggregated.astype({"node": "str", "age": "str", "state": "str"}))


def setup_logger(args: Optional[argparse.Namespace] = None) -> None:
    """
    Configure package-level logger instance.

    :param args: argparse.Namespace
        args.logfile (pathlib.Path) is used to create a logfile if present
        args.quiet and args.debug control logging level to sys.stderr

    This function can be called without args, in which case it configures the
    package logger to write WARNING and above to STDERR.

    When called with args, it uses args.logfile to determine if logs (by
    default, INFO and above) should be written to a file, and the path of
    that file. args.quiet and args.debug are used to control reporting
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
                "level": "INFO",
                "class": "logging.StreamHandler",
                "formatter": "standard",
                "stream": "ext://sys.stderr",
            },
        },
        "loggers": {__package__: {"handlers": ["stderr"], "level": "DEBUG"}},
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
        logconf["handlers"]["logfile"] = {  # type: ignore
            "class": "logging.FileHandler",
            "level": "INFO",
            "formatter": "standard",
            "filename": str(args.logfile),
            "encoding": "utf8",
        }
        logconf["loggers"][__package__]["handlers"].append("logfile")  # type: ignore

    # Set STDERR/logfile levels if args.quiet/args.debug specified
    if args is not None and args.quiet:
        logconf["handlers"]["stderr"]["level"] = "WARNING"  # type: ignore
    elif args is not None and args.debug:
        logconf["handlers"]["stderr"]["level"] = "DEBUG"  # type: ignore
        if "logfile" in logconf["handlers"]:  # type: ignore
            logconf["handlers"]["logfile"]["level"] = "DEBUG"  # type: ignore

    # Configure logger
    logging.config.dictConfig(logconf)


def build_args(argv):
    """Return parsed CLI arguments as argparse.Namespace.

    :param argv: CLI arguments
    :type argv: list
    """

    parser = argparse.ArgumentParser(
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
        description="Uses the deterministic network of populations model to simulation the disease progression",
    )
    parser.add_argument(
        "--use-movement-multipliers",
        action="store_true",
        help="By enabling this parameter you can adjust dampening or heightening people movement through time",
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
        "-q",
        "--quiet",
        dest="quiet",
        action="store_true",
        help="Prints only warnings to stderr",
    )
    parser.add_argument(
        "--debug", action="store_true", help="Provide debug output to STDERR"
    )
    parser.add_argument(
        "-c",
        "--data-pipeline-config",
        default="config.yaml",
        help="Base directory with the input parameters",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=0,
        help="Defaults to the number of CPUs in the machine",
    )

    return parser.parse_args(argv)


if __name__ == "__main__":
    # The logger name inherits from the package, if called as __main__
    logger = logging.getLogger(f"{__package__}.{__name__}")
    main(sys.argv[1:])
