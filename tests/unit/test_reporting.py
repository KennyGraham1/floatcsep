import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

import floatcsep.postprocess.reporting as reporting


class TestReportingGenerateReport(unittest.TestCase):
    @patch("floatcsep.postprocess.reporting.custom_report")
    def test_generate_report_with_custom_function(self, mock_custom_report):
        mock_experiment = MagicMock()
        mock_experiment.postprocess.get.return_value = "custom_report_function"

        reporting.generate_report(mock_experiment)

        mock_custom_report.assert_called_once_with("custom_report_function", mock_experiment)

    @patch("floatcsep.postprocess.reporting.markdown_to_pdf")
    @patch("floatcsep.postprocess.reporting.MarkdownReport")
    @patch("floatcsep.postprocess.reporting.plot_handler.parse_plot_config")
    def test_generate_standard_report(
        self, mock_parse_plot_config, mock_markdown_report, mock_markdown_to_pdf
    ):
        mock_parse_plot_config.return_value = {}

        mock_experiment = MagicMock()
        mock_experiment.postprocess.get.return_value = {}

        mock_experiment.registry.run_dir = Path("/tmp/run")
        mock_experiment.registry.get_figure_key.return_value = Path("figure.png")
        mock_experiment.magnitudes = [5.0, 6.0]
        mock_experiment.time_windows = [[1, 2]]
        mock_experiment.catalog_repo.catalog = object()
        mock_experiment.tests = []
        mock_experiment.models = []
        mock_experiment.start_date = "2020-01-01"
        mock_experiment.end_date = "2021-01-01"
        mock_experiment.name = "MyExperiment"

        reporting.generate_report(mock_experiment)

        mock_markdown_report.assert_called_once()
        mr = mock_markdown_report.return_value

        mr.add_title.assert_called_once_with("Experiment Report", "MyExperiment")
        mr.add_heading.assert_called()
        mr.add_list.assert_called()
        mr.table_of_contents.assert_called_once()
        mr.save.assert_called_once()

        mock_markdown_to_pdf.assert_called_once()


class TestMarkdownReport(unittest.TestCase):
    def test_add_title_writes_html_with_title_and_subtitle(self):
        report = reporting.MarkdownReport(root_dir=".")
        report.add_title("Experiment Report", "MyExperiment")
        text = report.to_markdown()

        self.assertIn("Experiment Report", text)
        self.assertIn("MyExperiment", text)
        self.assertIn("<img", text)
        self.assertIn("logo.png", text)

    def test_table_of_contents_uses_h2(self):
        report = reporting.MarkdownReport(root_dir=".")
        report.toc = [("Objectives", 2, "objectives")]
        report.table_of_contents()

        self.assertIn("## Table of Contents", report.markdown[0])
        self.assertIn("[Objectives](#objectives)", report.markdown[0])

    @patch("floatcsep.postprocess.reporting.Path.write_text")
    def test_save_report_uses_path_write_text(self, mock_write_text):
        report = reporting.MarkdownReport(root_dir=".")
        report.markdown = ["# Test Title\n", "Some content\n"]

        report.save("/path/to/save/report.md")

        mock_write_text.assert_called_once_with(
            "# Test Title\nSome content\n", encoding="utf-8"
        )


class TestHelpers(unittest.TestCase):
    @patch("floatcsep.postprocess.reporting.Image.open")
    def test_get_image_aspect(self, mock_image_open):
        mock_img = MagicMock()
        mock_img.size = (800, 400)
        mock_image_open.return_value.__enter__.return_value = mock_img

        aspect = reporting.get_image_aspect("dummy.png")
        self.assertAlmostEqual(aspect, 2.0)

    def test_width_fraction_from_aspect_single_column(self):
        self.assertAlmostEqual(reporting.width_fraction_from_aspect(None), 0.7)
        self.assertAlmostEqual(reporting.width_fraction_from_aspect(0.5), 0.6)
        self.assertAlmostEqual(reporting.width_fraction_from_aspect(1.0), 0.75)
        self.assertAlmostEqual(reporting.width_fraction_from_aspect(2.0), 0.9)

    def test_width_fraction_from_aspect_multi_column(self):
        frac = reporting.width_fraction_from_aspect(1.0, ncols=3)
        self.assertAlmostEqual(frac, (1.0 / 3.0) * 0.85)


class TestReportingHelpers(unittest.TestCase):
    @patch("floatcsep.postprocess.reporting.Image.open")
    def test_get_image_aspect_normal(self, mock_image_open):
        mock_img = MagicMock()
        mock_img.size = (800, 400)
        mock_image_open.return_value.__enter__.return_value = mock_img

        aspect = reporting.get_image_aspect("dummy.png")
        self.assertAlmostEqual(aspect, 2.0)

    @patch("floatcsep.postprocess.reporting.Image.open")
    def test_get_image_aspect_failure_returns_none(self, mock_image_open):
        mock_image_open.side_effect = Exception("boom")

        aspect = reporting.get_image_aspect("dummy.png")
        self.assertIsNone(aspect)

    def test_width_fraction_from_aspect_single_column(self):
        self.assertAlmostEqual(reporting.width_fraction_from_aspect(None), 0.7)
        self.assertAlmostEqual(reporting.width_fraction_from_aspect(0.5), 0.6)
        self.assertAlmostEqual(reporting.width_fraction_from_aspect(1.0), 0.75)
        self.assertAlmostEqual(reporting.width_fraction_from_aspect(2.0), 0.9)

    def test_width_fraction_from_aspect_multi_column(self):
        frac = reporting.width_fraction_from_aspect(1.0, ncols=3)
        self.assertAlmostEqual(frac, (1.0 / 3.0) * 0.85)


if __name__ == "__main__":
    unittest.main()
