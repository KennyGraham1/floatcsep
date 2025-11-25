import os

from floatcsep.postprocess.reporting import MarkdownReport
from floatcsep.utils.helpers import timewindow2str


def main(experiment):
    """

    Args:
        experiment: a floatcsep.experiment.Experiment class

    """

    report_path = experiment.registry.run_dir / "report.md"

    # Access the last time-window
    timewindow = experiment.time_windows[-1]

    # Convert the time-window to a string
    timestr = timewindow2str(timewindow)

    # Instantiates a Report object and adds a title and objectives
    report = MarkdownReport(root_dir=experiment.registry.run_dir)
    report.add_title(f"Experiment Report - {experiment.name}", "")
    report.add_heading("Objectives", level=2)

    objs = [
        f"Comparison of ETAS, pyMock-Poisson and pyMock-NegativeBinomial models for the "
        f"day after the Amatrice earthquake, for events with M>{min(experiment.magnitudes)}.",
    ]
    report.add_list(objs)

    # Adds an input figure
    cat_map_path = os.path.relpath(
        experiment.registry.get_figure_key("main_catalog_map"), report_path.parent
    )
    cat_time_path = os.path.relpath(
        experiment.registry.get_figure_key("main_catalog_time"), report_path.parent
    )
    report.add_heading("Catalog", level=2)
    report.add_figure(
        f"Input catalog",
        [cat_map_path, cat_time_path],
        level=3,
        ncols=1,
        caption=f"Evaluation catalog of {experiment.start_date}. "
        f"Earthquakes are filtered above Mw"
        f" {min(experiment.magnitudes)}.",
        add_ext=True,
    )

    # Include results from Experiment
    report.add_heading("Results", level=2)
    test = experiment.tests[0]
    for model in experiment.models:
        fig_path = os.path.relpath(
            experiment.registry.get_figure_key(timestr, f"{test.name}_{model.name}"),
            report_path.parent,
        )
        report.add_figure(
            f"{test.name}: {model.name}",
            fig_path,
            level=3,
            caption="Catalog-based N-test",
            add_ext=True,
            width=500,
        )

    # Stores the report
    report.save(report_path)
