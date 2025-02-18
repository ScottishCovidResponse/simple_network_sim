"""
Converts csv into hdf5 tables
"""
# pylint: disable=import-error
import argparse
import logging
import pathlib
import sys

from data_pipeline_api.file_formats import object_file  # type: ignore
import pandas as pd  # type: ignore

logger = logging.getLogger(f"{__package__}.{__name__}")


def main(argv):
    """
    Main function for the csv_to_hdf5 script, which converts a csv into a hdf5 table
    """
    parser = argparse.ArgumentParser(description="Converts a csv tabular file used by the model into a hdf5 file")
    parser.add_argument(
        "input_file",
        help="This is the path for the csv input file",
    )
    parser.add_argument(
        "output_file",
        help="This is the path for the hdf5 output file",
    )
    parser.add_argument(
        "-c",
        "--component",
        default=None,
        help="Component to use when creating the hdf5 file. If none provided, then the directory name containing the file (the product name) will be used"
    )
    args = parser.parse_args(argv)

    if args.component is None:
        component = find_component(pathlib.Path(args.input_file).resolve())
        logger.info("Using default component: %s", component)
    else:
        component = args.component
    with open(args.output_file, "w+b") as fp:
        object_file.write_table(fp, component, pd.read_csv(args.input_file))


def find_component(path: pathlib.PurePath):
    """
    Extracts the likely component name of a CSV file based on the path to it
    :param path: path to a CSV file
    :return: likely component to use
    """
    # pylint: disable=no-else-return
    if path.parent.name.isnumeric():
        # Probably a version directory
        return path.parents[1].name
    else:
        return path.parent.name


if __name__ == "__main__":
    logging.basicConfig(
        stream=sys.stdout,
        level=logging.INFO,
        format="[%(asctime)s] [%(name)s] [%(levelname)s] %(message)s",
    )
    main(sys.argv[1:])
