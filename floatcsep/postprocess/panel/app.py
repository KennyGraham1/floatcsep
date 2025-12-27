from pathlib import Path
from typing import Any, Optional
import panel as pn

from .manifest import build_manifest
from .layout import make_template_app


def run_app(
    experiment: Any,
    port: int = 0,
    address: str = "localhost",
    show: bool = True,
    title: Optional[str] = None,
    start: bool = True,
    **kwargs,
) -> None:
    pn.extension()

    manifest = build_manifest(experiment)
    app = make_template_app(manifest)

    if title is None:
        title = manifest.name

    panel_dir = Path(__file__).resolve().parent
    artifacts_dir = panel_dir.parent / "artifacts"

    pn.serve(
        app,
        address=address,
        port=port,
        show=show,
        title=title or manifest.name,
        static_dirs={"artifacts": str(artifacts_dir)},
        start=start,
        **kwargs
    )
