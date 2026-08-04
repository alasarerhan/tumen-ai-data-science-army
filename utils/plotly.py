import json

import plotly.io as pio


def plotly_from_dict(plotly_graph_dict: dict):
    """
    Converts a Plotly graph dictionary to a Plotly graph object

    Parameters
    -----------
    plotly_graph_dict: dict
        A plotly graph dictionary

    Returns
    --------
    plotly_graph: plotly.graph_objs.graph_objs.Figure
        A plotly graph object
    """
    if plotly_from_dict is None:
        return None

    return pio.from_json(json.dumps(plotly_graph_dict))
