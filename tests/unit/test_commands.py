import unittest
from unittest.mock import patch, MagicMock
import floatcsep.commands.main as main_module


class TestMainModule(unittest.TestCase):

    @patch("floatcsep.commands.main.Experiment")
    @patch("floatcsep.commands.main.plot_catalogs")
    @patch("floatcsep.commands.main.plot_forecasts")
    @patch("floatcsep.commands.main.plot_results")
    @patch("floatcsep.commands.main.plot_custom")
    @patch("floatcsep.commands.main.generate_report")
    def test_run(
        self,
        mock_generate_report,
        mock_plot_custom,
        mock_plot_results,
        mock_plot_forecasts,
        mock_plot_catalogs,
        mock_experiment,
    ):
        # Mock Experiment instance and its methods
        mock_exp_instance = MagicMock()
        mock_experiment.from_yml.return_value = mock_exp_instance

        # Call the function
        main_module.run(config="dummy_config")

        # Verify the calls to the Experiment class methods
        mock_experiment.from_yml.assert_called_once_with(config_yml="dummy_config")
        mock_exp_instance.stage_models.assert_called_once()
        mock_exp_instance.set_tasks.assert_called_once()
        mock_exp_instance.run.assert_called_once()

        # Verify that plotting and report generation functions were called
        mock_plot_catalogs.assert_called_once_with(experiment=mock_exp_instance)
        mock_plot_forecasts.assert_called_once_with(experiment=mock_exp_instance)
        mock_plot_results.assert_called_once_with(experiment=mock_exp_instance)
        mock_plot_custom.assert_called_once_with(experiment=mock_exp_instance)
        mock_generate_report.assert_called_once_with(experiment=mock_exp_instance)

    @patch("floatcsep.commands.main.Experiment")
    def test_stage(self, mock_experiment):
        # Mock Experiment instance and its methods
        mock_exp_instance = MagicMock()
        mock_experiment.from_yml.return_value = mock_exp_instance

        # Call the function
        main_module.stage(config="dummy_config")

        # Verify the calls to the Experiment class methods
        mock_experiment.from_yml.assert_called_once_with(config_yml="dummy_config")
        mock_exp_instance.stage_models.assert_called_once()

    @patch("floatcsep.commands.main.Experiment")
    @patch("floatcsep.commands.main.plot_catalogs")
    @patch("floatcsep.commands.main.plot_forecasts")
    @patch("floatcsep.commands.main.plot_results")
    @patch("floatcsep.commands.main.plot_custom")
    @patch("floatcsep.commands.main.generate_report")
    def test_plot(
        self,
        mock_generate_report,
        mock_plot_custom,
        mock_plot_results,
        mock_plot_forecasts,
        mock_plot_catalogs,
        mock_experiment,
    ):
        # Mock Experiment instance and its methods
        mock_exp_instance = MagicMock()
        mock_experiment.from_yml.return_value = mock_exp_instance

        # Call the function
        main_module.plot(config="dummy_config")

        # Verify the calls to the Experiment class methods
        mock_experiment.from_yml.assert_called_once_with(config_yml="dummy_config")
        mock_exp_instance.stage_models.assert_called_once()
        mock_exp_instance.set_tasks.assert_called_once()

        # Verify that plotting and report generation functions were called
        mock_plot_catalogs.assert_called_once_with(experiment=mock_exp_instance)
        mock_plot_forecasts.assert_called_once_with(experiment=mock_exp_instance)
        mock_plot_results.assert_called_once_with(experiment=mock_exp_instance)
        mock_plot_custom.assert_called_once_with(experiment=mock_exp_instance)
        mock_generate_report.assert_called_once_with(experiment=mock_exp_instance)

    @patch("floatcsep.commands.main.Experiment")
    @patch("floatcsep.commands.main.ExperimentComparison")
    @patch("floatcsep.commands.main.reproducibility_report")
    def test_reproduce(self, mock_reproducibility_report, mock_exp_comparison, mock_experiment):
        # Mock Experiment instances and methods
        mock_reproduced_exp = MagicMock()
        mock_original_exp = MagicMock()
        mock_experiment.from_yml.side_effect = [mock_reproduced_exp, mock_original_exp]

        mock_comp_instance = MagicMock()
        mock_exp_comparison.return_value = mock_comp_instance

        # Call the function
        main_module.reproduce(config="dummy_config")

        # Verify the calls to the Experiment class methods
        mock_experiment.from_yml.assert_any_call("dummy_config", repr_dir="reproduced")
        mock_reproduced_exp.stage_models.assert_called_once()
        mock_reproduced_exp.set_tasks.assert_called_once()
        mock_reproduced_exp.run.assert_called_once()

        mock_experiment.from_yml.assert_any_call(
            mock_reproduced_exp.original_config, run_dir=mock_reproduced_exp.original_run_dir
        )
        mock_original_exp.stage_models.assert_called_once()
        mock_original_exp.set_tasks.assert_called_once()

        # Verify comparison and reproducibility report calls
        mock_exp_comparison.assert_called_once_with(mock_original_exp, mock_reproduced_exp)
        mock_comp_instance.compare_results.assert_called_once()
        mock_reproducibility_report.assert_called_once_with(exp_comparison=mock_comp_instance)

    @patch("floatcsep.postprocess.nextjs.run_nextjs_app")
    @patch("floatcsep.commands.main.Experiment")
    def test_view_nextjs(self, mock_experiment, mock_run_nextjs_app):
        mock_exp_instance = MagicMock()
        mock_experiment.from_yml.return_value = mock_exp_instance

        main_module.view(config="dummy_config", ui="nextjs", address="0.0.0.0", port=8080)

        mock_experiment.from_yml.assert_called_once_with(config_yml="dummy_config")
        mock_exp_instance.stage_models.assert_called_once()
        mock_exp_instance.set_tree.assert_called_once()
        mock_run_nextjs_app.assert_called_once_with(
            experiment=mock_exp_instance, address="0.0.0.0", port=8080
        )

    @patch("floatcsep.commands.main.run_app")
    @patch("floatcsep.commands.main.Experiment")
    def test_view_panel(self, mock_experiment, mock_run_app):
        mock_exp_instance = MagicMock()
        mock_experiment.from_yml.return_value = mock_exp_instance

        # By default, only this machine
        main_module.view(config="dummy_config")
        mock_run_app.assert_called_once_with(
            experiment=mock_exp_instance, address="localhost", port=0
        )

        # Served to other machines, whose browsers' websockets Bokeh must accept
        mock_run_app.reset_mock()
        main_module.view(config="dummy_config", address="0.0.0.0", port=8080)
        mock_run_app.assert_called_once_with(
            experiment=mock_exp_instance, address="0.0.0.0", port=8080, websocket_origin="*"
        )

    @patch("floatcsep.commands.main.view")
    def test_cli_view_address_port(self, mock_view):
        argv = ["floatcsep", "view", "config.yml", "--ui", "nextjs"]
        with patch("sys.argv", argv + ["--address", "0.0.0.0", "--port", "8080"]):
            main_module.floatcsep()
        kwargs = mock_view.call_args.kwargs
        self.assertEqual(kwargs["address"], "0.0.0.0")
        self.assertEqual(kwargs["port"], 8080)

        # Not given: left to view's defaults
        mock_view.reset_mock()
        with patch("sys.argv", argv):
            main_module.floatcsep()
        self.assertNotIn("address", mock_view.call_args.kwargs)
        self.assertNotIn("port", mock_view.call_args.kwargs)

    @patch("floatcsep.commands.main.run")
    def test_cli_address_port_only_for_view(self, mock_run):
        with patch("sys.argv", ["floatcsep", "run", "config.yml", "--port", "8080"]):
            with self.assertRaises(SystemExit):
                main_module.floatcsep()
        mock_run.assert_not_called()


if __name__ == "__main__":
    unittest.main()
