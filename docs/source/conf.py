# Configuration file for the Sphinx documentation builder.
#
# For the full list of built-in configuration values, see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html
from __future__ import annotations

import os
import sys
import tomllib

sys.path.insert(0, os.path.abspath("../../"))

# -- Project information -----------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#project-information

with open(os.path.abspath("../../rossum-mcp/pyproject.toml"), "rb") as f:
    _pyproject = tomllib.load(f)

project = "Rossum MCP Server"
copyright = "2025, Dan Stancl"
author = "Dan Stancl"
version = _pyproject["project"]["version"]
release = version

# -- General configuration ---------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#general-configuration

extensions = [
    "sphinx.ext.autodoc",
    "sphinx.ext.napoleon",
    "sphinx.ext.viewcode",
    "sphinx.ext.intersphinx",
    "sphinx.ext.todo",
    "sphinx.ext.coverage",
    "sphinx_autodoc_typehints",
    "myst_parser",
    "sphinx_copybutton",
]

# Autodoc settings
autodoc_default_options = {
    "members": True,
    "member-order": "bysource",
    "special-members": "__init__",
    "undoc-members": True,
    "exclude-members": "__weakref__",
    "show-inheritance": True,
}

# Additional autodoc settings
autodoc_member_order = "bysource"
autodoc_typehints = "description"
autodoc_typehints_description_target = "documented"
autoclass_content = "both"  # Include both class and __init__ docstrings

# Napoleon settings (for Google/NumPy style docstrings)
napoleon_google_docstring = True
napoleon_numpy_docstring = True
napoleon_include_init_with_doc = True
napoleon_include_private_with_doc = False
napoleon_include_special_with_doc = True
napoleon_use_admonition_for_examples = True
napoleon_use_admonition_for_notes = True
napoleon_use_admonition_for_references = True
napoleon_use_ivar = False
napoleon_use_param = True
napoleon_use_rtype = True
napoleon_preprocess_types = False
napoleon_type_aliases = None
napoleon_attr_annotations = True

# Intersphinx mapping
intersphinx_mapping = {
    "python": ("https://docs.python.org/3", None),
}

# MyST parser settings
myst_enable_extensions = [
    "colon_fence",
    "deflist",
    "substitution",
    "tasklist",
]

templates_path = ["_templates"]
exclude_patterns = []

# -- Options for HTML output -------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#options-for-html-output

html_theme = "furo"
html_static_path = ["_static"]
html_logo = "_static/rossum-logo.svg"
html_favicon = "_static/rossum-logo.svg"
html_title = "Rossum MCP Server"

html_theme_options = {
    "light_css_variables": {
        "color-brand-primary": "#1E6EE5",
        "color-brand-content": "#1E6EE5",
        "color-admonition-background": "rgba(30, 110, 229, 0.05)",
        "color-sidebar-background": "#ffffff",
        "color-sidebar-search-background": "#f5f7fa",
        "color-sidebar-search-border": "#e0e6ed",
        "color-sidebar-link-text--top-level": "#0d1117",
        "color-sidebar-item-background--hover": "rgba(30, 110, 229, 0.08)",
        "color-sidebar-item-expander-background--hover": "rgba(30, 110, 229, 0.08)",
        "font-stack": "-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif",
        "font-stack--monospace": "'SFMono-Regular', Menlo, Consolas, 'Liberation Mono', monospace",
    },
    "dark_css_variables": {
        "color-brand-primary": "#61A0FF",
        "color-brand-content": "#61A0FF",
        "color-admonition-background": "rgba(97, 160, 255, 0.1)",
    },
    "sidebar_hide_name": False,
    "navigation_with_keys": True,
    "top_of_page_buttons": ["view"],
    "source_repository": "https://github.com/stancld/rossum-agents",
    "source_branch": "master",
    "source_directory": "docs/source/",
}

# -- Options for todo extension ----------------------------------------------
todo_include_todos = True


# Custom CSS and JS
def setup(app):
    app.add_css_file("custom.css")
    app.add_js_file("custom.js")
