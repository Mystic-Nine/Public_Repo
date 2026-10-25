#!/usr/bin/env python3
from bot import CMD_SUFFIX, config_dict

class _BotCommands:
    def __init__(self):
        self.StartCommand = 'start'
        self.LeechCommand = [f'leech{CMD_SUFFIX}', f'l{CMD_SUFFIX}']
        if config_dict['SHOW_EXTRA_CMDS']:
            self.LeechCommand.extend([f'unzipleech{CMD_SUFFIX}', f'uzl{CMD_SUFFIX}', f'zipleech{CMD_SUFFIX}', f'zl{CMD_SUFFIX}'])
        self.CancelTask = f'cancel{CMD_SUFFIX}'
        self.CancelAllCommand = [f'cancelall{CMD_SUFFIX}', 'cancellallbot']
        self.StatusCommand = [f'status{CMD_SUFFIX}', f's{CMD_SUFFIX}', 'statusall']
        self.UsersCommand = f'users{CMD_SUFFIX}'
        self.AuthorizeCommand = [f'authorize{CMD_SUFFIX}', f'a{CMD_SUFFIX}']
        self.UnAuthorizeCommand = [f'unauthorize{CMD_SUFFIX}', f'ua{CMD_SUFFIX}']
        self.AddBlackListCommand = [f'blacklist{CMD_SUFFIX}', f'bl{CMD_SUFFIX}']
        self.RmBlackListCommand = [f'rmblacklist{CMD_SUFFIX}', f'rbl{CMD_SUFFIX}']
        self.AddSudoCommand = f'addsudo{CMD_SUFFIX}'
        self.RmSudoCommand = f'rmsudo{CMD_SUFFIX}'
        self.ViewSudoCommand = f'viewsudo{CMD_SUFFIX}'
        self.PingCommand = [f'ping{CMD_SUFFIX}', f'p{CMD_SUFFIX}']
        self.RestartCommand = [f'restart{CMD_SUFFIX}', f'r{CMD_SUFFIX}', 'restartall']
        self.StatsCommand = [f'stats{CMD_SUFFIX}', f'st{CMD_SUFFIX}']
        self.HelpCommand = f'help{CMD_SUFFIX}'
        self.LogCommand = f'log{CMD_SUFFIX}'
        self.ShellCommand = f'shell{CMD_SUFFIX}'
        self.EvalCommand = f'eval{CMD_SUFFIX}'
        self.ExecCommand = f'exec{CMD_SUFFIX}'
        self.ClearLocalsCommand = f'clearlocals{CMD_SUFFIX}'
        self.BotSetCommand = [f'bsetting{CMD_SUFFIX}', f'bs{CMD_SUFFIX}']
        self.UserSetCommand = [f'usetting{CMD_SUFFIX}', f'us{CMD_SUFFIX}']
        self.SpeedCommand = [f'speedtest{CMD_SUFFIX}', f'sp{CMD_SUFFIX}']
        self.LoginCommand = 'login'
        self.AddImageCommand = f'addimg{CMD_SUFFIX}'
        self.ImagesCommand = f'images{CMD_SUFFIX}'
        self.IMDBCommand = f'imdb{CMD_SUFFIX}'
        self.AniListCommand = f'anime{CMD_SUFFIX}'
        self.AnimeHelpCommand = f'animehelp{CMD_SUFFIX}'
        self.MediaInfoCommand = [f'mediainfo{CMD_SUFFIX}', f'mi{CMD_SUFFIX}']
        self.MyDramaListCommand = f'mdl{CMD_SUFFIX}'
        self.PosterCommand = f'poster{CMD_SUFFIX}'
        self.AutoRenameCommand = f'autorename{CMD_SUFFIX}'
        self.SetThumbCommand = f't{CMD_SUFFIX}'
        self.BroadcastCommand = [f'broadcast{CMD_SUFFIX}', f'bc{CMD_SUFFIX}']

BotCommands = _BotCommands()
