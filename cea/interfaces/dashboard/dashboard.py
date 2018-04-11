from flask import Flask
from importlib import import_module

import cea.config


def register_blueprints(app):
    for module_name in ('forms', 'ui', 'home', 'tables', 'data', 'additional', 'base'):
        module = import_module('cea.interfaces.plots.{}.routes'.format(module_name))
        app.register_blueprint(module.blueprint)


def list_tools():
    """List the tools known to the CEA. The result is grouped by category.
    """
    import cea.scripts
    from itertools import groupby

    tools = sorted(cea.scripts.for_interface('dashboard'), key=lambda t: t.category)
    result = {}
    for category, group in groupby(tools, lambda t: t.category):
        result[category] = [t for t in group]
    return result


def main(config):
    app = Flask(__name__, static_folder='base/static')
    app.config.from_mapping({'DEBUG': True,
                             'SECRET_KEY': 'secret'})

    # provide the list of tools
    @app.context_processor
    def tools_processor():
        return dict(tools=list_tools())

    import cea.interfaces.dashboard.base.routes
    import cea.interfaces.dashboard.home.routes
    import cea.interfaces.dashboard.tools.routes
    import cea.interfaces.dashboard.plots.routes

    app.register_blueprint(cea.interfaces.dashboard.base.routes.blueprint)
    app.register_blueprint(cea.interfaces.dashboard.home.routes.blueprint)
    app.register_blueprint(cea.interfaces.dashboard.tools.routes.blueprint)
    app.register_blueprint(cea.interfaces.dashboard.plots.routes.blueprint)

    # keep a copy of the configuration we're using
    app.cea_config = config

    # keep a list of running scripts - (Process, Connection)
    # the protocol for the Connection messages is tuples ('stdout'|'stderr', str)
    app.workers = {} # script-name -> (Process, Connection)

    app.run(host='0.0.0.0', port=config.dashboard.port, threaded=False)


if __name__ == '__main__':
    main(cea.config.Configuration())