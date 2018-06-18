#!/usr/bin/env python
# -*- coding:utf-8 -*-

from __future__ import print_function, absolute_import

import os
import platform
import re
import sys
import shlex
import subprocess

import click
import six

from click import echo, MultiCommand, Option, Argument, ParamType

__version__ = '0.3.1'

_invalid_ident_char_re = re.compile(r'[^a-zA-Z0-9_]')


class CompletionConfiguration(object):
    """A class to hold the completion configuration

    Attributes
    ----------

    complete_options : bool
        Wether to complete the options or not. By default, the options are only completed after the user has entered
        a first dash '-'. Change this value to True to always complete the options, even without first typing any
        character.
    """
    def __init__(self):
        self.complete_options = False


completion_configuration = CompletionConfiguration()


def resolve_ctx(cli, prog_name, args):
    """

    Parameters
    ----------
    cli : click.Command
        The main click Command of the program
    prog_name : str
        The program name on the command line
    args : [str]
        The arguments already written by the user on the command line

    Returns
    -------
    click.core.Context
        A new context corresponding to the current command
    """
    ctx = cli.make_context(prog_name, list(args), resilient_parsing=True)
    while ctx.args + ctx.protected_args and isinstance(ctx.command, MultiCommand):
        a = ctx.protected_args + ctx.args
        cmd = ctx.command.get_command(ctx, a[0])
        if cmd is None:
            return None
        ctx = cmd.make_context(a[0], a[1:], parent=ctx, resilient_parsing=True)
    return ctx


def startswith(string, incomplete):
    """Returns True when string starts with incomplete

    It might be overridden with a fuzzier version - for example a case insensitive version

    Parameters
    ----------
    string : str
        The string to check
    incomplete : str
        The incomplete string to compare to the begining of string

    Returns
    -------
    bool
        True if string starts with incomplete, False otherwise
    """
    return string.startswith(incomplete)


def get_choices(cli, prog_name, args, incomplete):
    """

    Parameters
    ----------
    cli : click.Command
        The main click Command of the program
    prog_name : str
        The program name on the command line
    args : [str]
        The arguments already written by the user on the command line
    incomplete : str
        The partial argument to complete

    Returns
    -------
    [(str, str)]
        A list of completion results. The first element of each tuple is actually the argument to complete, the second
        element is an help string for this argument.
    """
    ctx = resolve_ctx(cli, prog_name, args)
    if ctx is None:
        return
    optctx = None
    if args:
        options = [param
                   for param in ctx.command.get_params(ctx)
                   if isinstance(param, Option)]
        arguments = [param
                     for param in ctx.command.get_params(ctx)
                     if isinstance(param, Argument)]
        for param in options:
            if not param.is_flag and args[-1] in param.opts + param.secondary_opts:
                optctx = param
        if optctx is None:
            for param in arguments:
                if (
                        not incomplete.startswith("-")
                        and (
                            ctx.params.get(param.name) in (None, ())
                            or param.nargs == -1
                        )
                ):
                    optctx = param
                    break
    choices = []
    if optctx:
        choices += [c if isinstance(c, tuple) else (c, None) for c in optctx.type.complete(ctx, incomplete)]
    else:
        for param in ctx.command.get_params(ctx):
            if (completion_configuration.complete_options or incomplete and not incomplete[:1].isalnum()) and isinstance(param, Option):
                for opt in param.opts:
                    if startswith(opt, incomplete):
                        choices.append((opt, param.help))
                for opt in param.secondary_opts:
                    if startswith(opt, incomplete):
                        # don't put the doc so fish won't group the primary and
                        # and secondary options
                        choices.append((opt, None))
        if isinstance(ctx.command, MultiCommand):
            for name in ctx.command.list_commands(ctx):
                if startswith(name, incomplete):
                    choices.append((name, ctx.command.get_command_short_help(ctx, name)))

    for item, help in choices:
        yield (item, help)


def split_args(line):
    """Version of shlex.split that silently accept incomplete strings.

    Parameters
    ----------
    line : str
        The string to split

    Returns
    -------
    [str]
        The line split in separated arguments
    """
    lex = shlex.shlex(line, posix=True)
    lex.whitespace_split = True
    lex.commenters = ''
    res = []
    try:
        while True:
            res.append(next(lex))
    except ValueError:  # No closing quotation
        pass
    except StopIteration:  # End of loop
        pass
    if lex.token:
        res.append(lex.token)
    return res


def do_bash_complete(cli, prog_name):
    """Do the completion for bash

    Parameters
    ----------
    cli : click.Command
        The main click Command of the program
    prog_name : str
        The program name on the command line

    Returns
    -------
    bool
        True if the completion was successful, False otherwise
    """
    comp_words = os.environ['COMP_WORDS']
    try:
        cwords = shlex.split(comp_words)
        quoted = False
    except ValueError:  # No closing quotation
        cwords = split_args(comp_words)
        quoted = True
    cword = int(os.environ['COMP_CWORD'])
    args = cwords[1:cword]
    try:
        incomplete = cwords[cword]
    except IndexError:
        incomplete = ''
    choices = get_choices(cli, prog_name, args, incomplete)

    if quoted:
        echo('\t'.join(opt for opt, _ in choices), nl=False)
    else:
        echo('\t'.join(re.sub(r"""([\s\\"'])""", r'\\\1', opt) for opt, _ in choices), nl=False)

    return True


def do_fish_complete(cli, prog_name):
    """Do the fish completion

    Parameters
    ----------
    cli : click.Command
        The main click Command of the program
    prog_name : str
        The program name on the command line

    Returns
    -------
    bool
        True if the completion was successful, False otherwise
    """
    commandline = os.environ['COMMANDLINE']
    args = split_args(commandline)[1:]
    if args and not commandline.endswith(' '):
        incomplete = args[-1]
        args = args[:-1]
    else:
        incomplete = ''

    for item, help in get_choices(cli, prog_name, args, incomplete):
        if help:
            echo("%s\t%s" % (item, re.sub('\s', ' ', help)))
        else:
            echo(item)

    return True


def do_zsh_complete(cli, prog_name):
    """Do the zsh completion

    Parameters
    ----------
    cli : click.Command
        The main click Command of the program
    prog_name : str
        The program name on the command line

    Returns
    -------
    bool
        True if the completion was successful, False otherwise
    """
    commandline = os.environ['COMMANDLINE']
    args = split_args(commandline)[1:]
    if args and not commandline.endswith(' '):
        incomplete = args[-1]
        args = args[:-1]
    else:
        incomplete = ''

    def escape(s):
        return s.replace('"', '""').replace("'", "''").replace('$', '\\$')
    res = []
    for item, help in get_choices(cli, prog_name, args, incomplete):
        if help:
            res.append('"%s"\:"%s"' % (escape(item), escape(help)))
        else:
            res.append('"%s"' % escape(item))
    if res:
        echo("_arguments '*: :((%s))'" % '\n'.join(res))
    else:
        echo("_files")

    return True


def do_powershell_complete(cli, prog_name):
    """Do the powershell completion

    Parameters
    ----------
    cli : click.Command
        The main click Command of the program
    prog_name : str
        The program name on the command line

    Returns
    -------
    bool
        True if the completion was successful, False otherwise
    """
    commandline = os.environ['COMMANDLINE']
    args = split_args(commandline)[1:]
    quote = single_quote
    incomplete = ''
    if args and not commandline.endswith(' '):
        incomplete = args[-1]
        args = args[:-1]
        quote_pos = commandline.rfind(incomplete) - 1
        if quote_pos >= 0 and commandline[quote_pos] == '"':
            quote = double_quote

    for item, help in get_choices(cli, prog_name, args, incomplete):
        echo(quote(item))

    return True


find_unsafe = re.compile(r'[^\w@%+=:,./-]').search


def single_quote(s):
    """Escape a string with single quotes in order to be parsed as a single element by shlex

    Parameters
    ----------
    s : str
        The string to quote

    Returns
    -------
    str
       The quoted string
    """
    if not s:
        return "''"
    if find_unsafe(s) is None:
        return s

    # use single quotes, and put single quotes into double quotes
    # the string $'b is then quoted as '$'"'"'b'
    return "'" + s.replace("'", "'\"'\"'") + "'"


def double_quote(s):
    """Escape a string with double quotes in order to be parsed as a single element by shlex

    Parameters
    ----------
    s : str
        The string to quote

    Returns
    -------
    str
       The quoted string
    """
    if not s:
        return '""'
    if find_unsafe(s) is None:
        return s

    # use double quotes, and put double quotes into single quotes
    # the string $"b is then quoted as "$"'"'"b"
    return '"' + s.replace('"', '"\'"\'"') + '"'


# extend click completion features

def param_type_complete(self, ctx, incomplete):
    """Returns a set of possible completions values, along with their documentation string

    Default implementation of the complete method for click.types.ParamType just returns an empty list

    Parameters
    ----------
    ctx : click.core.Context
        The current context
    incomplete :
        The string to complete

    Returns
    -------
    [(str, str)]
        A list of completion results. The first element of each tuple is actually the argument to complete, the second
        element is an help string for this argument.
    """
    return []


def choice_complete(self, ctx, incomplete):
    """Returns the completion results for click.core.Choice

    Parameters
    ----------
    ctx : click.core.Context
        The current context
    incomplete :
        The string to complete

    Returns
    -------
    [(str, str)]
        A list of completion results
    """
    return [(c, None) for c in self.choices if c.startswith(incomplete)]


def multicommand_get_command_short_help(self, ctx, cmd_name):
    """Returns the short help of a subcommand

    It allows MultiCommand subclasses to implement more efficient ways to provide the subcommand short help, for
    example by leveraging some caching.

    Parameters
    ----------
    ctx : click.core.Context
        The current context
    cmd_name :
        The sub command name

    Returns
    -------
    str
        The sub command short help
    """
    return self.get_command(ctx, cmd_name).short_help


def _shellcomplete(cli, prog_name, complete_var=None):
    """Internal handler for the bash completion support.

    Parameters
    ----------
    cli : click.Command
        The main click Command of the program
    prog_name : str
        The program name on the command line
    complete_var : str
        The environment variable name used to control the completion behavior (Default value = None)
    """
    if complete_var is None:
        complete_var = '_%s_COMPLETE' % (prog_name.replace('-', '_')).upper()
    complete_instr = os.environ.get(complete_var)
    if not complete_instr:
        return

    if complete_instr == 'source':
        echo(get_code(prog_name=prog_name, env_name=complete_var))
    elif complete_instr == 'source-bash':
        echo(get_code('bash', prog_name, complete_var))
    elif complete_instr == 'source-fish':
        echo(get_code('fish', prog_name, complete_var))
    elif complete_instr == 'source-powershell':
        echo(get_code('powershell', prog_name, complete_var))
    elif complete_instr == 'source-zsh':
        echo(get_code('zsh', prog_name, complete_var))
    elif complete_instr in ['complete', 'complete-bash']:
        # keep 'complete' for bash for backward compatibility
        do_bash_complete(cli, prog_name)
    elif complete_instr == 'complete-fish':
        do_fish_complete(cli, prog_name)
    elif complete_instr == 'complete-powershell':
        do_powershell_complete(cli, prog_name)
    elif complete_instr == 'complete-zsh':
        do_zsh_complete(cli, prog_name)
    elif complete_instr == 'install':
        shell, path = install(prog_name=prog_name, env_name=complete_var)
        click.echo('%s completion installed in %s' % (shell, path))
    elif complete_instr == 'install-bash':
        shell, path = install(shell='bash', prog_name=prog_name, env_name=complete_var)
        click.echo('%s completion installed in %s' % (shell, path))
    elif complete_instr == 'install-fish':
        shell, path = install(shell='fish', prog_name=prog_name, env_name=complete_var)
        click.echo('%s completion installed in %s' % (shell, path))
    elif complete_instr == 'install-zsh':
        shell, path = install(shell='zsh', prog_name=prog_name, env_name=complete_var)
        click.echo('%s completion installed in %s' % (shell, path))
    elif complete_instr == 'install-powershell':
        shell, path = install(shell='powershell', prog_name=prog_name, env_name=complete_var)
        click.echo('%s completion installed in %s' % (shell, path))
    sys.exit()


_initialized = False


def init(complete_options=False):
    """Initialize the enhanced click completion

    Parameters
    ----------
    complete_options : bool
        always complete the options, even when the user hasn't typed a first dash (Default value = False)
    """
    global _initialized
    if not _initialized:
        import click
        click.types.ParamType.complete = param_type_complete
        click.types.Choice.complete = choice_complete
        click.core.MultiCommand.get_command_short_help = multicommand_get_command_short_help
        click.core._bashcomplete = _shellcomplete
        completion_configuration.complete_options = complete_options
        _initialized = True


class DocumentedChoice(ParamType):
    """The choice type allows a value to be checked against a fixed set of
    supported values.  All of these values have to be strings. Each value may
    be associated to a help message that will be display in the error message
    and during the completion.

    Parameters
    ----------
    choices : dict
        A dictionary with the possible choice as key, and the corresponding help string as value
    """
    name = 'choice'

    def __init__(self, choices):
        self.choices = dict(choices)

    def get_metavar(self, param):
        return '[%s]' % '|'.join(self.choices.keys())

    def get_missing_message(self, param):
        formated_choices = ['{:<12} {}'.format(k, self.choices[k] or '') for k in sorted(self.choices.keys())]
        return 'Choose from\n  ' + '\n  '.join(formated_choices)

    def convert(self, value, param, ctx):
        # Exact match
        if value in self.choices:
            return value

        # Match through normalization
        if ctx is not None and \
           ctx.token_normalize_func is not None:
            value = ctx.token_normalize_func(value)
            for choice in self.choices:
                if ctx.token_normalize_func(choice) == value:
                    return choice

        self.fail('invalid choice: %s. %s' %
                  (value, self.get_missing_message(param)), param, ctx)

    def __repr__(self):
        return 'DocumentedChoice(%r)' % list(self.choices.keys())

    def complete(self, ctx, incomplete):
        return [(c, v) for c, v in six.iteritems(self.choices) if startswith(c, incomplete)]


def get_code(shell=None, prog_name=None, env_name=None, extra_env=None):
    """Returns the completion code to be evaluated by the shell

    Parameters
    ----------
    shell : str
        The shell type. Possible values are 'bash', 'fish', 'zsh' and 'powershell' (Default value = None)
    prog_name : str
        The program name on the command line (Default value = None)
    env_name : str
        The environment variable used to control the completion (Default value = None)
    extra_env : dict
        Some extra environment variables to be added to the generated code (Default value = None)

    Returns
    -------
    str
        The code to be evaluated by the shell
    """
    from jinja2 import Environment, FileSystemLoader
    if shell in [None, 'auto']:
        shell = get_auto_shell()
    prog_name = prog_name or click.get_current_context().find_root().info_name
    env_name = env_name or '_%s_COMPLETE' % prog_name.upper().replace('-', '_')
    extra_env = extra_env if extra_env else {}
    env = Environment(loader=FileSystemLoader(os.path.dirname(__file__)))
    template = env.get_template('%s.j2' % shell)
    return template.render(prog_name=prog_name, complete_var=env_name, extra_env=extra_env)


def get_auto_shell():
    """Returns the current shell

    This feature depends on psutil and will not work if it is not available"""
    try:
        import psutil
        parent = psutil.Process(os.getpid()).parent()
        if platform.system() == 'Windows':
            parent = parent.parent() or parent
        return parent.name().replace('.exe', '')
    except ImportError:
        raise click.UsageError("Please explicitly give the shell type or install the psutil package to activate the"
                               " automatic shell detection.")


def install(shell=None, prog_name=None, env_name=None, path=None, append=None, extra_env=None):
    """Install the completion

    Parameters
    ----------
    shell : str
        The shell type targeted. It will be guessed with get_auto_shell() if the value is None. Possible values are
        'bash', 'fish', 'zsh' and 'powershell' (Default value = None)
    prog_name : str
        The program name on the command line. It will be automatically computed if the value is None
        (Default value = None)
    env_name : str
        The environment variable name used to control the completion. It will be automatically computed if the value is
        None (Default value = None)
    path : str
        The installation path of the code to be evaluated by the shell. The standard installation path is used if the
        value is None (Default value = None)
    append : bool
        Whether to append the content to the file or to override it. The default behavior depends on the shell type
        (Default value = None)
    extra_env : dict
        A set of environment variables and their values to be added to the generated code (Default value = None)
    """
    prog_name = prog_name or click.get_current_context().find_root().info_name
    shell = shell or get_auto_shell()
    if append is None and path is not None:
        append = True
    if append is not None:
        mode = 'a' if append else 'w'
    else:
        mode = None

    if shell == 'fish':
        path = path or os.path.expanduser('~') + '/.config/fish/completions/%s.fish' % prog_name
        mode = mode or 'w'
    elif shell == 'bash':
        path = path or os.path.expanduser('~') + '/.bash_completion'
        mode = mode or 'a'
    elif shell == 'zsh':
        ohmyzsh = os.path.expanduser('~') + '/.oh-my-zsh'
        if os.path.exists(ohmyzsh):
            path = path or ohmyzsh + '/completions/_%s' % prog_name
            mode = mode or 'w'
        else:
            path = path or os.path.expanduser('~') + '/.zshrc'
            mode = mode or 'a'
    elif shell == 'powershell':
        subprocess.check_call(['powershell', 'Set-ExecutionPolicy Unrestricted -Scope CurrentUser'])
        path = path or subprocess.check_output(['powershell', '-NoProfile', 'echo $profile']).strip() if install else ''
        mode = mode or 'a'
    else:
        raise click.ClickException('%s is not supported.' % shell)

    if append is not None:
        mode = 'a' if append else 'w'
    else:
        mode = mode
    d = os.path.dirname(path)
    if not os.path.exists(d):
        os.makedirs(d)
    f = open(path, mode)
    f.write(get_code(shell, prog_name, env_name, extra_env))
    f.write("\n")
    f.close()
    return shell, path


shells = {
    'bash': 'Bourne again shell',
    'fish': 'Friendly interactive shell',
    'zsh': 'Z shell',
    'powershell': 'Windows PowerShell'
}
