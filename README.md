# log-watch
Python log watcher, that allows running custom actions.

Script watch files that match unix path pattern. It can:
* distinguish rotating log files (new filewith already known name),
* automatically watching new files that match pattern,
* forgetting deleted, moved or renamed files (if path pattern doesn't match),
* printing 'n' last chars of new files.

You can add as many callback as you want. Each callback will be executed once for every new line.
Lines order is maintaned per file. Callbacks can maintain its state if needed.
