# conftest.py — pytest configuration for the Finance Intelligence System.
#
# This file is automatically loaded by pytest before any tests run.
# It adds the project root to sys.path so all modules (config, analysis,
# chatbot, etc.) can be imported without installation.
#
# This is the standard pattern for pytest in a src-less project layout.

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
