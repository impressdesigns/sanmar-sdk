"""Configuration file for the Sphinx documentation builder.

For the full list of built-in configuration values, see the documentation:
https://www.sphinx-doc.org/en/master/usage/configuration.html
"""

from importlib.metadata import metadata

project_metadata = metadata("idi-sanmar-sdk")
project: str = project_metadata["Name"]
release: str = project_metadata["Version"]
REPO_LINK: str = project_metadata["Project-URL"].replace("repository, ", "")
copyright: str = "Impress Designs"  # noqa: A001
author: str = "Impress Designs team"

# Add any Sphinx extension module names here, as strings. They can be
# extensions coming with Sphinx (named "sphinx.ext.*") or your custom
# ones.
extensions = [
    "sphinx.ext.autodoc",
    "sphinx.ext.linkcode",
    "sphinx.ext.intersphinx",
    "sphinx.ext.napoleon",
    "autoapi.extension",
    "releases",
]

autoapi_type: str = "python"
autoapi_dirs: list[str] = ["../src"]
# The default options plus nothing private: the wire payloads and SOAP plumbing are
# implementation details, and publishing them would invite callers to depend on them.
autoapi_options: list[str] = [
    "members",
    "undoc-members",
    "show-inheritance",
    "show-module-summary",
    "special-members",
    "imported-members",
]

intersphinx_mapping = {
    "python": ("https://docs.python.org/3", None),
    "paramiko": ("https://docs.paramiko.org/en/stable", None),
    "pydantic": ("https://docs.pydantic.dev/latest", None),
    "requests": ("https://requests.readthedocs.io/en/latest", None),
    "zeep": ("https://docs.python-zeep.org/en/master", None),
}

# Field limits are declared as ``Annotated[str, Field(...)]``, which autoapi renders with
# pydantic's ``Field`` unqualified, so there is nothing for it to resolve against.
# Type parameters of generic functions and aliases (PEP 695) are not documented objects
# either, and neither is what a generic alias expands to. The service classes are built by
# the client from its private connection and login, whose types stay unpublished.
nitpick_ignore: list[tuple[str, str]] = [
    ("py:class", "Field"),
    ("py:class", "R"),
    ("py:class", "T"),
    ("py:class", "BeforeValidator"),
    ("py:class", "_as_list"),
    ("py:class", "SoapClient"),
    ("py:class", "Credentials"),
    ("py:obj", "sanmar_sdk._soap.Service"),
]

# List of patterns, relative to source directory, that match files and
# directories to ignore when looking for source files.
# This pattern also affects html_static_path and html_extra_path.
exclude_patterns: list[str] = ["_build", "Thumbs.db", ".DS_Store"]

# -- Options for HTML output -------------------------------------------------

# The theme to use for HTML and HTML Help pages.  See the documentation for
# a list of builtin themes.
html_theme: str = "furo"

releases_github_path = REPO_LINK.removeprefix("https://github.com/")
releases_release_uri = f"{REPO_LINK}/releases/tag/v%s"


def linkcode_resolve(domain: str, info: dict) -> str | None:
    """linkcode_resolve."""
    if domain != "py":
        return None
    if not info["module"]:
        return None

    import importlib  # noqa: PLC0415
    import inspect  # noqa: PLC0415
    import types  # noqa: PLC0415

    mod = importlib.import_module(info["module"])

    val = mod
    for k in info["fullname"].split("."):
        val = getattr(val, k, None)
        if val is None:
            break

    filename = info["module"].replace(".", "/") + ".py"

    if isinstance(
        val,
        types.ModuleType
        | types.MethodType
        | types.FunctionType
        | types.TracebackType
        | types.FrameType
        | types.CodeType,
    ):
        try:
            lines, first = inspect.getsourcelines(val)
            last = first + len(lines) - 1
            filename += f"#L{first}-L{last}"
        except OSError, TypeError:
            # getsourcelines raises OSError when it cannot locate the source (C extensions,
            # dynamically constructed objects) and TypeError for builtins. Neither is worth
            # failing a docs build over, so fall back to linking the file without an anchor.
            pass

    return f"{REPO_LINK}/blob/main/src/{filename}"
