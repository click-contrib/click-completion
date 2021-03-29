#!/usr/bin/env python
# -*- coding:utf-8 -*-

from __future__ import print_function, absolute_import

import os
import re
import shlex
import subprocess

import click
from click import Option, Argument, MultiCommand, echo
from enum import Enum

from click_completion.lib import resolve_ctx, split_args, single_quote, double_quote, get_auto_shell


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


class CompletionConfiguration(object):
    """A class to hold the completion configuration

    Attributes
    ----------

    complete_options : bool
        Wether to complete the options or not. By default, the options are only completed after the user has entered
        a first dash '-'. Change this value to True to always complete the options, even without first typing any
        character.
    match_incomplete : func
        A function use to check whether a parameter match an incomplete argument typed by the user
    """
    def __init__(self):
        self.complete_options = False
        self.match_incomplete = startswith


def match(string, incomplete):
    import click_completion
    # backward compatibility handling
    if click_completion.startswith != startswith:
        fn = click_completion.startswith
    else:
        fn = completion_configuration.match_incomplete
    return fn(string, incomplete)


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
                # filter hidden click.Option
                if getattr(param, 'hidden', False):
                    continue
                for opt in param.opts:
                    if match(opt, incomplete):
                        choices.append((opt, param.help))
                for opt in param.secondary_opts:
                    if match(opt, incomplete):
                        # don't put the doc so fish won't group the primary and
                        # and secondary options
                        choices.append((opt, None))
        if isinstance(ctx.command, MultiCommand):
            for name in ctx.command.list_commands(ctx):
                if match(name, incomplete):
                    choices.append((name, ctx.command.get_command_short_help(ctx, name)))

    for item, help in choices:
        yield (item, help)


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
        echo('\t'.join(re.sub(r"""([\s\\"'()])""", r'\\\1', opt) for opt, _ in choices), nl=False)

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
            echo("%s\t%s" % (item, re.sub(r'\s', ' ', help)))
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
        return s.replace('"', '""').replace("'", "''").replace('$', '\\$').replace('`', '\\`')
    res = []
    for item, help in get_choices(cli, prog_name, args, incomplete):
        if help:
            res.append(r'"%s"\:"%s"' % (escape(item), escape(help)))
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


def get_code(shell=None, prog_name=None, env_name=None, extra_env=None):
    """Returns the completion code to be evaluated by the shell

    Parameters
    ----------
    shell : Shell
        The shell type (Default value = None)
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
    if not isinstance(shell, Shell):
        shell = Shell[shell]
    prog_name = prog_name or click.get_current_context().find_root().info_name
    env_name = env_name or '_%s_COMPLETE' % prog_name.upper().replace('-', '_')
    extra_env = extra_env if extra_env else {}
    env = Environment(loader=FileSystemLoader(os.path.dirname(__file__)))
    template = env.get_template('%s.j2' % shell.name)
    return template.render(prog_name=prog_name, complete_var=env_name, extra_env=extra_env)


class InstallConfiguration(object):
    """A class to hold the installation configuration for auto completion.

    Attributes
    ----------
    prog_name : str
        The program name on the command line.
    shell : Shell
        The shell type targeted.
    path : str
        The installation path of the code to be evaluated by the shell.
    mode : str
        Whether to append the content to the file or to override it.
    code : str
        The completion code to be written to the installation path.
    """
    def __init__(self, shell=None, prog_name=None, env_name=None, path=None, append=None, extra_env=None):
        """
        Parameters
        ----------
        shell : Shell
            The shell type targeted. It will be guessed with get_auto_shell() if the value is None (Default value = None)
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

        Raises
        -------
        click.ClickException
            If the provided Shell isn't supported.
        """
        self.prog_name = prog_name or click.get_current_context().find_root().info_name
        self.shell = shell or get_auto_shell()
        self.path, self.mode = self.__get_path_config(shell, prog_name, path, append)
        self.code = get_code(shell, prog_name, env_name, extra_env)

    def __get_path_config(self, shell=None, prog_name=None, path=None, append=None):
        """
        Determines the path and write mode for the given shell.

        Parameters
        ----------
        shell : Shell
            The shell type targeted.
        prog_name : str
            The program name on the command line.
        path : str
            The installation path of the code to be evaluated by the shell.
        append : bool
            Whether to append the content to the file or to override it.

        Returns
        -------
        Tuple[str, str]
            The path and write mode for writing the completion code.

        Raises
        -------
        click.ClickException
            If the provided Shell isn't supported.

        """
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
            path = path or os.path.expanduser('~') + '/.zshrc'
            mode = mode or 'a'
        elif shell == 'powershell':
            subprocess.check_call(['powershell', 'Set-ExecutionPolicy Unrestricted -Scope CurrentUser'])
            path = path or subprocess.check_output(
                ['powershell', '-NoProfile', 'echo $profile']).strip() if install else ''
            mode = mode or 'a'
        else:
            raise click.ClickException('%s is not supported.' % shell)

        if append is not None:
            mode = 'a' if append else 'w'
        else:
            mode = mode

        return path, mode


def install(shell=None, prog_name=None, env_name=None, path=None, append=None, extra_env=None):
    """Install the completion

    Parameters
    ----------
    shell : Shell
        The shell type targeted. It will be guessed with get_auto_shell() if the value is None (Default value = None)
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

    Returns
    -------
    Tuple[str, str]
        The current shell and the path the code completion was written to.

    Raises
    -------
    click.ClickException
        If the provided Shell isn't supported.
    """
    install_config = InstallConfiguration(shell, prog_name, env_name, path, append, extra_env)
    return install_from_config(install_config)


def install_from_config(install_config):
    """Install the auto completion from an InstallConfiguration object.

    Parameters
    ----------
    install_config : InstallConfiguration
        The object that holds the configuration with the auto completion settings.

    Returns
    -------
    Tuple[str, str]
        The current shell and the path the code completion was written to.
    """
    d = os.path.dirname(install_config.path)
    if not os.path.exists(d):
        os.makedirs(d)
    f = open(install_config.path, install_config.mode)
    f.write(install_config.code)
    f.write("\n")
    f.close()
    return install_config.shell, install_config.path


class Shell(Enum):
    bash = 'Bourne again shell'
    fish = 'Friendly interactive shell'
    zsh = 'Z shell'
    powershell = 'Windows PowerShell'


# deprecated - use Shell instead
shells = dict((shell.name, shell.value) for shell in Shell)


completion_configuration = CompletionConfiguration()
