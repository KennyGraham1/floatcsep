import importlib.util
import re
import logging
import os
from typing import TYPE_CHECKING
import numpy
from markdown_pdf import MarkdownPdf, Section
from floatcsep.experiment import ExperimentComparison
from floatcsep.utils.helpers import timewindow2str, str2timewindow
from floatcsep.postprocess import plot_handler

if TYPE_CHECKING:
    from floatcsep.experiment import Experiment


log = logging.getLogger("floatLogger")

"""
Use the MarkdownReport class to create output for the experiment.

1. string templates are stored for each evaluation
2. string templates are stored for each forecast
3. report should include
    - plots of catalog
    - plots of forecasts
    - evaluation results
    - metadata from run, (maybe json dump of Experiment class)
"""


def generate_report(experiment, timewindow=-1):

    report_function = experiment.postprocess.get("report")
    if report_function:
        custom_report(report_function, experiment)
        return

    report_path = experiment.registry.run_dir / "report.md"

    all_windows = list(experiment.time_windows)
    if timewindow == 0:
        windows = all_windows
    else:
        windows = [all_windows[timewindow]]

    show_tw_heading = len(all_windows) > 1

    log.info(f"Saving report into {experiment.registry.run_dir}")

    report = MarkdownReport()
    report.add_title(f"Experiment Report - {experiment.name}", "")
    report.add_heading("Objectives", level=2)
    objs = [
        "Describe the predictive skills of posited hypothesis about "
        "seismogenesis with earthquakes of"
        f" M>{min(experiment.magnitudes)}.",
    ]
    report.add_list(objs)

    # Generate catalog plot
    plot_catalog: dict = plot_handler.parse_plot_config(
        experiment.postprocess.get("plot_catalog", {})
    )
    report.add_heading("Authoritative Data", level=2)
    if experiment.catalog_repo.catalog is not None:
        cat_map_path = os.path.relpath(
            experiment.registry.get_figure_key("main_catalog_map"), report_path.parent
        )
        cat_time_path = os.path.relpath(
            experiment.registry.get_figure_key("main_catalog_time"), report_path.parent
        )
        report.add_figure(
            "Input catalog",
            [cat_map_path, cat_time_path],
            level=3,
            ncols=1,
            caption="Evaluation catalog from "
            f"{experiment.start_date} until {experiment.end_date}. "
            f"Earthquakes are filtered above Mw"
            f" {min(experiment.magnitudes)}.",
            add_ext=True,
            width=plot_catalog.get("figsize", [4])[0] * 148,
        )

    # Include forecasts
    plot_forecasts: dict = plot_handler.parse_plot_config(
        experiment.postprocess.get("plot_forecasts", {})
    )

    if isinstance(plot_forecasts, dict):
        report.add_heading("Forecasts", level=2)
        for tw in windows:
            tw_str = timewindow2str(tw)
            if show_tw_heading:
                report.add_heading(f"Forecasts for {tw_str}", level=3)
            model_level = 4 if show_tw_heading else 3

            for model in experiment.models:
                fpath = os.path.relpath(
                    experiment.registry.get_figure_key(tw_str, "forecasts", model.name),
                    report_path.parent,
                )
                report.add_figure(
                    title=f"{model.name}",
                    relative_filepaths=fpath,
                    level=model_level,
                    add_ext=True,
                    width=plot_forecasts.get("figsize", [4])[0] * 126,
                )

    # Include results from Experiment
    report.add_heading("Test results", level=2)
    for tw in windows:
        tw_str = timewindow2str(tw)
        if show_tw_heading:
            report.add_heading(f"Results for {tw_str}", level=3)
        test_level = 4 if show_tw_heading else 3
        model_level = test_level + 1

        for test in experiment.tests:
            fig_path = os.path.relpath(
                experiment.registry.get_figure_key(tw_str, test), report_path.parent
            )
            width = test.plot_args[0].get("figsize", [4])[0] * 96

            report.add_figure(
                f"{test.name}",
                fig_path,
                level=test_level,
                caption=test.markdown,
                add_ext=True,
                width=width,
            )
            for model in experiment.models:
                try:
                    model_fig_path = os.path.relpath(
                        experiment.registry.get_figure_key(tw_str, f"{test.name}_{model.name}"),
                        report_path.parent,
                    )
                    width = test.plot_args[0].get("figsize", [4])[0] * 96
                    report.add_figure(
                        f"{model.name}",
                        model_fig_path,
                        level=model_level,
                        caption=test.markdown,
                        add_ext=True,
                        width=width,
                    )
                except KeyError:
                    pass

    report.table_of_contents()
    report.save(report_path)

    md_text = report.to_markdown()
    pdf = MarkdownPdf(toc_level=2, optimize=True)
    section = Section(md_text, root=str(report_path.parent))
    pdf.add_section(section)
    pdf.meta["title"] = f"Experiment Report - {experiment.name}"
    pdf.meta["author"] = "floatCSEP"

    pdf_path = (experiment.registry.run_dir / "report.pdf").as_posix()
    pdf.save(pdf_path)


def reproducibility_report(exp_comparison: "ExperimentComparison"):

    numerical = exp_comparison.num_results
    data = exp_comparison.file_comp

    report_path = (
        exp_comparison.reproduced.registry.workdir
        / exp_comparison.reproduced.registry.run_dir
        / "reproducibility_report.md"
    )

    report = MarkdownReport()
    report.add_title(f"Reproducibility Report - {exp_comparison.original.name}", "")

    report.add_heading("Objectives", level=2)
    objs = [
        "Analyze the statistic reproducibility and data reproducibility of"
        " the experiment. Compares the differences between "
        "(i) the original and reproduced scores,"
        " (ii) the statistical descriptors of the test distributions,"
        " (iii) The p-value of a Kolmogorov-Smirnov test -"
        " values beneath 0.1 means we can't reject the distributions are"
        " similar -,"
        " (iv) Hash (SHA-256) comparison between the results' files and "
        "(v) byte-to-byte comparison"
    ]

    report.add_list(objs)
    for num, dat in zip(numerical.items(), data.items()):

        res_keys = list(num[1].keys())
        is_time = False
        try:
            str2timewindow(res_keys[0])
            is_time = True
        except ValueError:
            pass
        if is_time:
            report.add_heading(num[0], level=2)
            for tw in res_keys:
                rows = [
                    [
                        tw,
                        "Score difference",
                        "Test Mean  diff.",
                        "Test Std  diff.",
                        "Test Skew  diff.",
                        "KS-test p value",
                        "Hash (SHA-256) equal",
                        "Byte-to-byte equal",
                    ]
                ]

                for model_stat, model_file in zip(num[1][tw].items(), dat[1][tw].items()):
                    obs = model_stat[1]["observed_statistic"]
                    test = model_stat[1]["test_statistic"]
                    rows.append(
                        [
                            model_stat[0],
                            obs,
                            *[f"{i:.1e}" for i in test[:-1]],
                            f"{test[-1]:.1e}",
                            model_file[1]["hash"],
                            model_file[1]["byte2byte"],
                        ]
                    )
                report.add_table(rows)
        else:
            report.add_heading(num[0], level=2)
            rows = [
                [
                    res_keys[-1],
                    "Max Score difference",
                    "Hash (SHA-256) equal",
                    "Byte-to-byte equal",
                ]
            ]

            for model_stat, model_file in zip(num[1].items(), dat[1].items()):
                obs = numpy.nanmax(model_stat[1]["observed_statistic"])

                rows.append(
                    [
                        model_stat[0],
                        f"{obs:.1e}",
                        model_file[1]["hash"],
                        model_file[1]["byte2byte"],
                    ]
                )

            report.add_table(rows)
    report.table_of_contents()
    report.save(report_path)


def custom_report(report_function: str, experiment: "Experiment"):

    try:
        script_path, func_name = report_function.split(".py:")
        script_path += ".py"

    except ValueError:
        log.error(
            f"Invalid format for custom plot function: {report_function}. "
            "Try {script_name}.py:{func}"
        )
        log.info(
            "\t Skipping reporting. The configuration script can be modified and re-run the"
            " reporting (and plots) only by typing 'floatcsep plot {config}'"
        )
        return

    log.info(f"Creating report from script {script_path} and function {func_name}")
    script_abs_path = experiment.registry.abs(script_path)
    allowed_directory = os.path.dirname(experiment.registry.abs(experiment.config_file))

    if not os.path.isfile(script_path) or (
        os.path.dirname(script_abs_path) != os.path.realpath(allowed_directory)
    ):

        log.error(f"Script {script_path} is not in the configuration file directory.")
        log.info(
            "\t Skipping reporting. The script can be reallocated and re-run the reporting only"
            " by typing 'floatcsep plot {config}'"
        )
        return

    module_name = os.path.splitext(os.path.basename(script_abs_path))[0]
    spec = importlib.util.spec_from_file_location(module_name, script_abs_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    try:
        func = getattr(module, func_name)

    except AttributeError:
        log.error(f"Function {func_name} not found in {script_path}")
        log.info(
            "\t Skipping reporting. Report script can be modified and re-run the report only"
            " by typing 'floatcsep plot {config}'"
        )
        return

    try:
        func(experiment)
    except Exception as e:
        log.error(f"Error executing {func_name} from {script_path}: {e}")
        log.info(
            "\t Skipping reporting. Report script can be modified and re-run the report only"
            " by typing 'floatcsep plot {config}'"
        )
    return


class MarkdownReport:
    """Class to generate a Markdown report from a study."""

    def __init__(self):

        self.toc = []
        self.has_title = True
        self.has_introduction = False
        self.markdown = []

    def add_introduction(self, adict):
        """Generate document header from dictionary."""
        first = (
            f"# CSEP Testing Results: {adict['simulation_name']}  \n"
            f"**Forecast Name:** {adict['forecast_name']}  \n"
            f"**Simulation Start Time:** {adict['origin_time']}  \n"
            f"**Evaluation Time:** {adict['evaluation_time']}  \n"
            f"**Catalog Source:** {adict['catalog_source']}  \n"
            f"**Number Simulations:** {adict['num_simulations']}\n"
        )

        # used to determine to place TOC at beginning of document or after
        # introduction.

        self.has_introduction = True
        self.markdown.append(first)
        return first

    def add_text(self, text):
        """
        Text should be a list of strings where each string will be on its own.

        line. Each add_text command represents a paragraph.

        Args:
            text (list): lines to write
        Returns:
        """
        self.markdown.append("  ".join(text) + "\n\n")

    def add_figure(
        self,
        title,
        relative_filepaths,
        level=2,
        ncols=1,
        add_ext=False,
        text="",
        caption="",
        width=None,
    ):
        """
        This function expects a list of filepaths.

        If you want the output
        stacked, select a value of ncols. ncols should be divisible by
        filepaths.

        Args:
            width:
            caption:
            text:
            add_ext:
            ncols:
            title: name of the figure
            level (int): value 1-6 depending on the heading
            relative_filepaths (str or List[Tuple[str]]): list of paths in
                order to make table
        Returns:
        """
        # verify filepaths have proper extension should always be png
        is_single = False
        paths = []
        if isinstance(relative_filepaths, str):
            is_single = True
            paths.append(relative_filepaths)
        else:
            paths = relative_filepaths

        correct_paths = []
        if add_ext:
            for fp in paths:
                correct_paths.append(fp if fp.lower().endswith(".png") else fp + ".png")
        else:
            correct_paths = paths

        # generate new lists with size ncols
        formatted_paths = [
            correct_paths[i : i + ncols] for i in range(0, len(correct_paths), ncols)
        ]

        # convert str into a list, where each potential row is an iter not str
        def build_header(ncols):
            header = "| " + " | ".join([" "] * ncols) + " |"
            under = "| " + " | ".join(["---"] * ncols) + " |"
            return header + "\n" + under

        size_attr = f' width="{int(width)}"' if width else ""
        # size_attr = f' style="width:{int(width)}px;"' if width else ""
        # size_attr = (
        #     f' width="{int(width)}" style="width:{int(width)}px;max-width:100%;height:auto;"'
        #     if width
        #     else ""
        # )

        def add_to_row(_row):
            if len(_row) == 1:
                return f'<img src="{_row[0]}"{size_attr}/>'
            cells = [f'<img src="{item}"{size_attr}/>' for item in _row]
            return "| " + " | ".join(cells) + " |"

        level_string = f"{level * '#'}"
        result_cell = []
        locator = title.lower().replace(" ", "_")
        result_cell.append(f'{level_string} {title}  <a name="{locator}"></a>\n')
        result_cell.append(f"{text}\n")

        for i, row in enumerate(formatted_paths):
            if i == 0 and not is_single and ncols > 1:
                result_cell.append(build_header(len(row)))
            result_cell.append(add_to_row(row))

        result_cell.append("\n")
        result_cell.append(f"{caption}")

        self.markdown.append("\n".join(result_cell) + "\n")

        # generate metadata for TOC
        self.toc.append((title, level, locator))

    def add_heading(self, title, level=1, text="", add_toc=True):
        # multiplying char simply repeats it
        if isinstance(text, str):
            text = [text]
        cell = []
        level_string = f"{level * '#'}"
        locator = title.lower().replace(" ", "_")
        sub_heading = f'{level_string} {title} <a name="{locator}"></a>\n'
        cell.append(sub_heading)
        try:
            for item in list(text):
                cell.append(item)
        except Exception as ex:
            raise RuntimeWarning(f"Unable to add document subhead, text must be iterable. {ex}")
        self.markdown.append("\n".join(cell) + "\n")

        # generate metadata for TOC
        if add_toc:
            self.toc.append((title, level, locator))

    def add_list(self, _list):
        cell = []
        for item in _list:
            cell.append(f"* {item}")
        self.markdown.append("\n".join(cell) + "\n\n")

    def add_title(self, title, text):
        self.has_title = True
        self.add_heading(title, 1, text, add_toc=False)

    def table_of_contents(self):
        """Generates table of contents based on contents of document."""
        if len(self.toc) == 0:
            return
        toc = ["# Table of Contents"]

        for i, elem in enumerate(self.toc):
            title, level, locator = elem
            space = "   " * (level - 1)
            toc.append(f"{space}1. [{title}](#{locator})")
        insert_loc = 1 if self.has_title else 0
        self.markdown.insert(insert_loc, "\n".join(toc) + "\n\n")

    def add_table(self, data, use_header=True):
        """
        Generates table from HTML and styles using bootstrap class.

        Args:
           data List[Tuple[str]]: should be (nrows, ncols) in size. all rows
            should be the same sizes
        Returns:
            table (str): this can be added to subheading or other cell if
                desired.
        """
        table = ['<div class="table table-striped">', "<table>"]

        def make_header(row_):
            header = ["<tr>"]
            for item in row_:
                header.append(f"<th>{item}</th>")
            header.append("</tr>")
            return "\n".join(header)

        def add_row(row_):
            table_row = ["<tr>"]
            for item in row_:
                table_row.append(f"<td>{item}</td>")
            table_row.append("</tr>")
            return "\n".join(table_row)

        for i, row in enumerate(data):
            if i == 0 and use_header:
                table.append(make_header(row))
            else:
                table.append(add_row(row))
        table.append("</table>")
        table.append("</div>")
        table = "\n".join(table)
        self.markdown.append(table + "\n\n")

    def to_markdown(self) -> str:
        """Return the whole report as a single Markdown string."""
        return "".join(self.markdown)

    def save(self, out_path):
        with open(out_path, "w", encoding="utf-8") as f:
            f.write("".join(self.markdown))


def _scale_img_widths(md_text: str, factor: float) -> str:
    """
    Scale <img ... width="N"> (or width='N') by 'factor'.
    - Case-insensitive on 'width'
    - Preserves the original quote style and surrounding markup
    - Only touches numeric width attributes (no CSS)

    Example match: <img src="..." width="384"/>
    """

    # <img ... width = " 123 " > with optional spaces and single/double quotes
    pattern = re.compile(
        r'(?i)(<img\b[^>]*?\bwidth\s*=\s*)(["\'])(\d+(?:\.\d+)?)(\2)', re.IGNORECASE
    )

    def repl(m: re.Match) -> str:
        prefix = m.group(1)  # '<img ... width=' (up to the quote)
        quote = m.group(2)  # the quote char (either " or ')
        num = float(m.group(3))
        scaled = max(1, int(round(num * factor)))
        return f"{prefix}{quote}{scaled}{quote}"

    new_text, n = pattern.subn(repl, md_text)

    return new_text
