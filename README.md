# click-completion
Enhanced completion for Click

Add automatic completion support for [fish], [Zsh], [Bash] and
[PowerShell] to [Click].

## Activation

In order to activate the completion, you need to:

* initialize the `click_completion` module;
* inform your shell that completion is available for your script, and how.

### `click_completion` initialization

`click_completion` monkey-patches `click` in order to enhance the native
completion capabilities. This is done very simply:

    import click_completion
    click_completion.init()

Once done, your click application is ready for completion.

### Inform your shell

As click, the general way `click_completion` works is through a magic environment
variable called `_<PROG_NAME>_COMPLETE`, where `<PROG_NAME>` is your application
executable name in uppercase with dashes replaced by underscores.

If your tool is called foo-bar, then the magic variable is called
`_FOO_BAR_COMPLETE`. By exporting it with the `source` value it will spit out the
activation script which can be trivially activated.

For instance, to enable fish completion for your foo-bar script, this is what
you would need to put into your `~/.config/fish/completions/foo-bar.fish`

    eval (_FOO_BAR_COMPLETE=source-fish foo-bar)

From this point onwards, your script will have fish completion enabled.

## Activation Script

The above activation example will always invoke your application on startup.
This might be slowing down the shell activation time significantly if you have
many applications. Alternatively, you could also ship a file with the contents
of that, which is what Git and other systems are doing.

This can be easily accomplished:

    _FOO_BAR_COMPLETE=source-fish foo-bar > ~/.config/fish/completions/foo-bar.fish

## License

Licensed under the MIT, see LICENSE.


[fish]: https://fishshell.com
[Zsh]: http://www.zsh.org
[Bash]: https://www.gnu.org/software/bash
[PowerShell]: https://msdn.microsoft.com/en-us/powershell/mt173057.aspx
[Click]: http://click.pocoo.org
