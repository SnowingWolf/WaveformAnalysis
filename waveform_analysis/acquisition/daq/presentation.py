"""Notebook and terminal presentation entry points for DAQ analysis."""

from .daq_analyzer import DAQAnalyzer, _in_notebook, _ipydisplay

display_overview = DAQAnalyzer.display_overview
display_run_channel_details = DAQAnalyzer.display_run_channel_details

__all__ = ["display_overview", "display_run_channel_details"]
