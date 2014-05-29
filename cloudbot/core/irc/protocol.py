import asyncio
from asyncio.queues import Queue
import re


class IRCProtocol(asyncio.Protocol):
    def __init__(self, loop, logger, charset='utf8'):
        """
        :type ircconn: IRCConnection
        """
        self.message_queue = Queue(loop=loop)
        self.charset = charset
        self.logger = logger

        # input buffer
        self._input_buffer = b""

        # connected
        self._connected = False

        # transport
        self.transport = None

    def connection_made(self, transport):
        self.transport = transport
        self._connected = True

    def connection_lost(self, exc):
        self._connected = False
        if exc is None:
            # we've been closed intentionally, so don't reconnect
            return
        self.logger.exception("[{}] Connection lost.".format(self.readable_name))
        #asyncio.async(self.botconn.connect(), loop=self.loop)

    def eof_received(self):
        self._connected = False
        self.logger.info("[{}] EOF Received, reconnecting.".format(self.readable_name))
        #asyncio.async(self.botconn.connect(), loop=self.loop)
        return True

    def send_message(self, command, *args):
        message = IRCMessage(command, *args)
        self.logger.debug("sent: %r", message)
        self.transport.write(message.render().encode(self.charset) + b'\r\n')

    def handle_message(self, message):
        if message.command == 'PING':
            self.send_message('PONG', message.args[-1])

        elif message.command == 'RPL_WELCOME':
            # 001, first thing sent after registration
            if not self.registered:
                self.registered = True

        self.message_queue.put_nowait(message)

    def data_received(self, data):
        data = self._input_buffer + data
        while True:
            raw_message, delim, data = data.partition(b'\r\n')
            if not delim:
                # Incomplete message; stop here and wait for more
                self._input_buffer = raw_message
                return

            # TODO valerr
            message = IRCMessage.parse(raw_message.decode(self.charset))
            self.logger.debug("recv: %r", message)
            self.handle_message(message)


class IRCMessage:
    """A single IRC message, either sent or received.

    Despite how clueless the IRC protocol is about character encodings, this
    class deals only with strings, not bytes.  Decode elsewhere, thanks.
    """
    def __init__(self, command, *args, prefix=None):
        if command.isdigit():
            # TODO command can't be a number when coming from a client
            self.command = NUMERICS.get(command, command)
            self.numeric = command
        else:
            self.command = command
            self.numeric = None
        self.prefix = prefix
        self.args = args

        # TODO stricter validation: all str (?), last arg...

    def __repr__(self):
        prefix = ''
        if self.prefix:
            prefix = " via {}".format(self.prefix)

        if self.numeric and self.numeric != self.command:
            command = "{}/{}".format(self.numeric, self.command)
        else:
            command = self.command

        return "<{name}: {command} {args}{prefix}>".format(
            name=type(self).__name__,
            command=command,
            args=', '.join(repr(arg) for arg in self.args),
            prefix=prefix,
        )

    def render(self):
        """String representation of an IRC message.  DOES NOT include the
        trailing newlines.
        """
        parts = [self.command] + list(self.args)
        # TODO assert no spaces
        # TODO assert nothing else begins with colon!
        if self.args and ' ' in parts[-1]:
            parts[-1] = ':' + parts[-1]

        return ' '.join(parts)

    # Oh boy this is ugly!
    PATTERN = re.compile(
        r'''\A
        (?: : (?P<prefix>[^ ]+) [ ]+ )?
        (?P<command> \d{3} | [a-zA-Z]+ )
        (?P<args>
            (?: [ ]+ [^: \x00\r\n][^ \x00\r\n]* )*
        )
        (?:
            [ ]+ [:] (?P<trailing> [^\x00\r\n]*)
        )?
        [ ]*
        \Z''',
        flags=re.VERBOSE)

    @classmethod
    def parse(cls, string):
        """Parse an IRC message.  DOES NOT expect to receive the trailing
        newlines.
        """
        m = cls.PATTERN.match(string)
        if not m:
            raise ValueError(repr(string))

        argstr = m.group('args').lstrip(' ')
        if argstr:
            args = re.split(' +', argstr)
        else:
            args = []

        if m.group('trailing'):
            args.append(m.group('trailing'))

        return cls(m.group('command'), *args, prefix=m.group('prefix'))


# Mapping of useless numeric codes to slightly less useless symbolic names.
# References:
# https://www.alien.net.au/irc/irc2numerics.html
NUMERICS = {
    '001': 'RPL_WELCOME',
    '002': 'RPL_YOURHOST',
    '003': 'RPL_CREATED',
    '004': 'RPL_MYINFO',
    '001': 'RPL_WELCOME',
    '002': 'RPL_YOURHOST',
    '003': 'RPL_CREATED',
    '004': 'RPL_MYINFO',
    '004': 'RPL_MYINFO',
    #[obsolete] '005': 'RPL_BOUNCE',
    '005': 'RPL_ISUPPORT',
    #[UNREAL] '006': 'RPL_MAP',
    #[UNREAL] '007': 'RPL_MAPEND',
    '008': 'RPL_SNOMASK',
    '009': 'RPL_STATMEMTOT',
    '010': 'RPL_BOUNCE',
    #[obsolete] '010': 'RPL_STATMEM',
    '014': 'RPL_YOURCOOKIE',
    #[IRCU] '015': 'RPL_MAP',
    #[IRCU] '016': 'RPL_MAPMORE',
    #[IRCU] '017': 'RPL_MAPEND',
    '042': 'RPL_YOURID',
    '043': 'RPL_SAVENICK',
    '050': 'RPL_ATTEMPTINGJUNC',
    '051': 'RPL_ATTEMPTINGREROUTE',
    '200': 'RPL_TRACELINK',
    '201': 'RPL_TRACECONNECTING',
    '202': 'RPL_TRACEHANDSHAKE',
    '203': 'RPL_TRACEUNKNOWN',
    '204': 'RPL_TRACEOPERATOR',
    '205': 'RPL_TRACEUSER',
    '206': 'RPL_TRACESERVER',
    '207': 'RPL_TRACESERVICE',
    '208': 'RPL_TRACENEWTYPE',
    '209': 'RPL_TRACECLASS',
    #[obsolete] '210': 'RPL_TRACERECONNECT',
    '210': 'RPL_STATS',
    '211': 'RPL_STATSLINKINFO',
    '212': 'RPL_STATSCOMMANDS',
    # Basically all of these are varying states of conflicting and
    # inconsistent...  TODO?
    #'213': 'RPL_STATSCLINE',
    #'214': 'RPL_STATSNLINE',
    #'215': 'RPL_STATSILINE',
    #'216': 'RPL_STATSKLINE',
    #'217': 'RPL_STATSQLINE',
    #'217': 'RPL_STATSPLINE',
    #'218': 'RPL_STATSYLINE',
    #'219': 'RPL_ENDOFSTATS',
    #'220': 'RPL_STATSPLINE',
    #'220': 'RPL_STATSBLINE',
    #'221': 'RPL_UMODEIS',
    #'222': 'RPL_MODLIST',
    #'222': 'RPL_SQLINE_NICK',
    #'222': 'RPL_STATSBLINE',
    #'223': 'RPL_STATSELINE',
    #'223': 'RPL_STATSGLINE',
    #'224': 'RPL_STATSFLINE',
    #'224': 'RPL_STATSTLINE',
    #'225': 'RPL_STATSDLINE',
    #'225': 'RPL_STATSZLINE',
    #'225': 'RPL_STATSELINE',
    #'226': 'RPL_STATSCOUNT',
    #'226': 'RPL_STATSNLINE',
    #'227': 'RPL_STATSGLINE',
    #'227': 'RPL_STATSVLINE',
    #'228': 'RPL_STATSQLINE',
    #'231': 'RPL_SERVICEINFO',
    #'232': 'RPL_ENDOFSERVICES',
    #'232': 'RPL_RULES',
    #'233': 'RPL_SERVICE',
    #'234': 'RPL_SERVLIST',
    #'235': 'RPL_SERVLISTEND',
    #'236': 'RPL_STATSVERBOSE',
    #'237': 'RPL_STATSENGINE',
    #'238': 'RPL_STATSFLINE',
    #'239': 'RPL_STATSIAUTH',
    #'240': 'RPL_STATSVLINE',
    #'240': 'RPL_STATSXLINE',
    #'241': 'RPL_STATSLLINE',
    #'242': 'RPL_STATSUPTIME',
    #'243': 'RPL_STATSOLINE',
    #'244': 'RPL_STATSHLINE',
    #'245': 'RPL_STATSSLINE',
    #'246': 'RPL_STATSPING',
    #'246': 'RPL_STATSTLINE',
    #'246': 'RPL_STATSULINE',
    #'247': 'RPL_STATSBLINE',
    #'247': 'RPL_STATSXLINE',
    #'247': 'RPL_STATSGLINE',
    #'248': 'RPL_STATSULINE',
    #'248': 'RPL_STATSDEFINE',
    #'249': 'RPL_STATSULINE',
    #'249': 'RPL_STATSDEBUG',
    #'250': 'RPL_STATSDLINE',
    #'250': 'RPL_STATSCONN',
    '251': 'RPL_LUSERCLIENT',
    '252': 'RPL_LUSEROP',
    '253': 'RPL_LUSERUNKNOWN',
    '254': 'RPL_LUSERCHANNELS',
    '255': 'RPL_LUSERME',
    '256': 'RPL_ADMINME',
    '257': 'RPL_ADMINLOC1',
    '258': 'RPL_ADMINLOC2',
    '259': 'RPL_ADMINEMAIL',
    '261': 'RPL_TRACELOG',
    #[conflict] '262': 'RPL_TRACEPING',
    #[conflict] '262': 'RPL_TRACEEND',
    '263': 'RPL_TRYAGAIN',
    '265': 'RPL_LOCALUSERS',
    '266': 'RPL_GLOBALUSERS',
    '267': 'RPL_START_NETSTAT',
    '268': 'RPL_NETSTAT',
    '269': 'RPL_END_NETSTAT',
    '270': 'RPL_PRIVS',
    '271': 'RPL_SILELIST',
    '272': 'RPL_ENDOFSILELIST',
    '273': 'RPL_NOTIFY',
    #[conflict] '274': 'RPL_ENDNOTIFY',
    #[conflict] '274': 'RPL_STATSDELTA',
    #'275': 'RPL_STATSDLINE',
    '276': 'RPL_VCHANEXIST',
    '277': 'RPL_VCHANLIST',
    '278': 'RPL_VCHANHELP',
    '280': 'RPL_GLIST',
    # Ridiculous piles of conflicts ahoy!
    #'281': 'RPL_ENDOFGLIST',
    #'281': 'RPL_ACCEPTLIST',
    #'282': 'RPL_ENDOFACCEPT',
    #'282': 'RPL_JUPELIST',
    #'283': 'RPL_ALIST',
    #'283': 'RPL_ENDOFJUPELIST',
    #'284': 'RPL_ENDOFALIST',
    #'284': 'RPL_FEATURE',
    #'285': 'RPL_GLIST_HASH',
    #'285': 'RPL_CHANINFO_HANDLE',
    #'285': 'RPL_NEWHOSTIS',
    #'286': 'RPL_CHANINFO_USERS',
    #'286': 'RPL_CHKHEAD',
    #'287': 'RPL_CHANINFO_CHOPS',
    #'287': 'RPL_CHANUSER',
    #'288': 'RPL_CHANINFO_VOICES',
    #'288': 'RPL_PATCHHEAD',
    #'289': 'RPL_CHANINFO_AWAY',
    #'289': 'RPL_PATCHCON',
    #'290': 'RPL_CHANINFO_OPERS',
    #'290': 'RPL_HELPHDR',
    #'290': 'RPL_DATASTR',
    #'291': 'RPL_CHANINFO_BANNED',
    #'291': 'RPL_HELPOP',
    #'291': 'RPL_ENDOFCHECK',
    #'292': 'RPL_CHANINFO_BANS',
    #'292': 'RPL_HELPTLR',
    #'293': 'RPL_CHANINFO_INVITE',
    #'293': 'RPL_HELPHLP',
    #'294': 'RPL_CHANINFO_INVITES',
    #'294': 'RPL_HELPFWD',
    #'295': 'RPL_CHANINFO_KICK',
    #'295': 'RPL_HELPIGN',
    '296': 'RPL_CHANINFO_KICKS',
    '299': 'RPL_END_CHANINFO',
    '300': 'RPL_NONE',
    '301': 'RPL_AWAY',
    '301': 'RPL_AWAY',
    '302': 'RPL_USERHOST',
    '303': 'RPL_ISON',
    #[???] '304': 'RPL_TEXT',
    '305': 'RPL_UNAWAY',
    '306': 'RPL_NOWAWAY',
    # More conflicts
    #'307': 'RPL_USERIP',
    #'307': 'RPL_WHOISREGNICK',
    #'307': 'RPL_SUSERHOST',
    #'308': 'RPL_NOTIFYACTION',
    #'308': 'RPL_WHOISADMIN',
    #'308': 'RPL_RULESSTART',
    #'309': 'RPL_NICKTRACE',
    #'309': 'RPL_WHOISSADMIN',
    #'309': 'RPL_ENDOFRULES',
    #'309': 'RPL_WHOISHELPER',
    #'310': 'RPL_WHOISSVCMSG',
    #'310': 'RPL_WHOISHELPOP',
    #'310': 'RPL_WHOISSERVICE',
    '311': 'RPL_WHOISUSER',
    '312': 'RPL_WHOISSERVER',
    '313': 'RPL_WHOISOPERATOR',
    '314': 'RPL_WHOWASUSER',
    '315': 'RPL_ENDOFWHO',
    #[obsolete] '316': 'RPL_WHOISCHANOP',
    '317': 'RPL_WHOISIDLE',
    '318': 'RPL_ENDOFWHOIS',
    '319': 'RPL_WHOISCHANNELS',
    '320': 'RPL_WHOISVIRT',
    '320': 'RPL_WHOIS_HIDDEN',
    '320': 'RPL_WHOISSPECIAL',
    #[obsolete] '321': 'RPL_LISTSTART',
    '322': 'RPL_LIST',
    '323': 'RPL_LISTEND',
    '324': 'RPL_CHANNELMODEIS',
    #[conflict] '325': 'RPL_UNIQOPIS',
    #[conflict] '325': 'RPL_CHANNELPASSIS',
    '326': 'RPL_NOCHANPASS',
    '327': 'RPL_CHPASSUNKNOWN',
    '328': 'RPL_CHANNEL_URL',
    '329': 'RPL_CREATIONTIME',
    #[conflict] '330': 'RPL_WHOWAS_TIME',
    #[conflict] '330': 'RPL_WHOISACCOUNT',
    '331': 'RPL_NOTOPIC',
    '332': 'RPL_TOPIC',
    '333': 'RPL_TOPICWHOTIME',
    #[conflict] '334': 'RPL_LISTUSAGE',
    #[conflict] '334': 'RPL_COMMANDSYNTAX',
    #[conflict] '334': 'RPL_LISTSYNTAX',
    #[conflict] '335': 'RPL_WHOISBOT',
    #[conflict] '338': 'RPL_CHANPASSOK',
    #[conflict] '338': 'RPL_WHOISACTUALLY',
    '339': 'RPL_BADCHANPASS',
    '340': 'RPL_USERIP',
    '341': 'RPL_INVITING',
    #[obsolete] '342': 'RPL_SUMMONING',
    '345': 'RPL_INVITED',
    '346': 'RPL_INVITELIST',
    '347': 'RPL_ENDOFINVITELIST',
    '348': 'RPL_EXCEPTLIST',
    '349': 'RPL_ENDOFEXCEPTLIST',
    '351': 'RPL_VERSION',
    '352': 'RPL_WHOREPLY',
    '353': 'RPL_NAMREPLY',
    '354': 'RPL_WHOSPCRPL',
    '355': 'RPL_NAMREPLY_',
    #[AUSTHEX] '357': 'RPL_MAP',
    #[AUSTHEX] '358': 'RPL_MAPMORE',
    #[AUSTHEX] '359': 'RPL_MAPEND',
    #[obsolete] '361': 'RPL_KILLDONE',
    #[obsolete] '362': 'RPL_CLOSING',
    #[obsolete] '363': 'RPL_CLOSEEND',
    '364': 'RPL_LINKS',
    '365': 'RPL_ENDOFLINKS',
    '366': 'RPL_ENDOFNAMES',
    '367': 'RPL_BANLIST',
    '368': 'RPL_ENDOFBANLIST',
    '369': 'RPL_ENDOFWHOWAS',
    '371': 'RPL_INFO',
    '372': 'RPL_MOTD',
    #[obsolete] '373': 'RPL_INFOSTART',
    '374': 'RPL_ENDOFINFO',
    '375': 'RPL_MOTDSTART',
    '376': 'RPL_ENDOFMOTD',
    #'377': 'RPL_KICKEXPIRED',
    #'377': 'RPL_SPAM',
    #'378': 'RPL_BANEXPIRED',
    #'378': 'RPL_WHOISHOST',
    #'378': 'RPL_MOTD',
    #'379': 'RPL_KICKLINKED',
    #'379': 'RPL_WHOISMODES',
    #'380': 'RPL_BANLINKED',
    #'380': 'RPL_YOURHELPER',
    '381': 'RPL_YOUREOPER',
    '382': 'RPL_REHASHING',
    '383': 'RPL_YOURESERVICE',
    #'384': 'RPL_MYPORTIS',
    '385': 'RPL_NOTOPERANYMORE',
    #'386': 'RPL_QLIST',
    #'386': 'RPL_IRCOPS',
    #'387': 'RPL_ENDOFQLIST',
    #'387': 'RPL_ENDOFIRCOPS',
    '388': 'RPL_ALIST',
    '389': 'RPL_ENDOFALIST',
    '391': 'RPL_TIME',
    '392': 'RPL_USERSSTART',
    '393': 'RPL_USERS',
    '394': 'RPL_ENDOFUSERS',
    '395': 'RPL_NOUSERS',
    '396': 'RPL_HOSTHIDDEN',
    '400': 'ERR_UNKNOWNERROR',
    '401': 'ERR_NOSUCHNICK',
    '402': 'ERR_NOSUCHSERVER',
    '403': 'ERR_NOSUCHCHANNEL',
    '404': 'ERR_CANNOTSENDTOCHAN',
    '405': 'ERR_TOOMANYCHANNELS',
    '406': 'ERR_WASNOSUCHNICK',
    '407': 'ERR_TOOMANYTARGETS',
    '408': 'ERR_NOSUCHSERVICE',
    #'408': 'ERR_NOCOLORSONCHAN',
    '409': 'ERR_NOORIGIN',
    '411': 'ERR_NORECIPIENT',
    '412': 'ERR_NOTEXTTOSEND',
    '413': 'ERR_NOTOPLEVEL',
    '414': 'ERR_WILDTOPLEVEL',
    '415': 'ERR_BADMASK',
    '416': 'ERR_TOOMANYMATCHES',
    '416': 'ERR_QUERYTOOLONG',
    '419': 'ERR_LENGTHTRUNCATED',
    '421': 'ERR_UNKNOWNCOMMAND',
    '422': 'ERR_NOMOTD',
    '423': 'ERR_NOADMININFO',
    '424': 'ERR_FILEERROR',
    '425': 'ERR_NOOPERMOTD',
    '429': 'ERR_TOOMANYAWAY',
    '430': 'ERR_EVENTNICKCHANGE',
    '431': 'ERR_NONICKNAMEGIVEN',
    '432': 'ERR_ERRONEUSNICKNAME',
    '433': 'ERR_NICKNAMEINUSE',
    #'434': 'ERR_SERVICENAMEINUSE',
    #'434': 'ERR_NORULES',
    #'435': 'ERR_SERVICECONFUSED',
    #'435': 'ERR_BANONCHAN',
    '436': 'ERR_NICKCOLLISION',
    #'437': 'ERR_UNAVAILRESOURCE',
    #'437': 'ERR_BANNICKCHANGE',
    #'438': 'ERR_NICKTOOFAST',
    #'438': 'ERR_DEAD',
    '439': 'ERR_TARGETTOOFAST',
    '440': 'ERR_SERVICESDOWN',
    '441': 'ERR_USERNOTINCHANNEL',
    '442': 'ERR_NOTONCHANNEL',
    '443': 'ERR_USERONCHANNEL',
    '444': 'ERR_NOLOGIN',
    '445': 'ERR_SUMMONDISABLED',
    '446': 'ERR_USERSDISABLED',
    '447': 'ERR_NONICKCHANGE',
    '449': 'ERR_NOTIMPLEMENTED',
    '451': 'ERR_NOTREGISTERED',
    '452': 'ERR_IDCOLLISION',
    '453': 'ERR_NICKLOST',
    '455': 'ERR_HOSTILENAME',
    '456': 'ERR_ACCEPTFULL',
    '457': 'ERR_ACCEPTEXIST',
    '458': 'ERR_ACCEPTNOT',
    '459': 'ERR_NOHIDING',
    '460': 'ERR_NOTFORHALFOPS',
    '461': 'ERR_NEEDMOREPARAMS',
    '462': 'ERR_ALREADYREGISTERED',
    '463': 'ERR_NOPERMFORHOST',
    '464': 'ERR_PASSWDMISMATCH',
    '465': 'ERR_YOUREBANNEDCREEP',
    '467': 'ERR_KEYSET',
    #'468': 'ERR_INVALIDUSERNAME',
    #'468': 'ERR_ONLYSERVERSCANCHANGE',
    '469': 'ERR_LINKSET',
    #'470': 'ERR_LINKCHANNEL',
    #'470': 'ERR_KICKEDFROMCHAN',
    '471': 'ERR_CHANNELISFULL',
    '472': 'ERR_UNKNOWNMODE',
    '473': 'ERR_INVITEONLYCHAN',
    '474': 'ERR_BANNEDFROMCHAN',
    '475': 'ERR_BADCHANNELKEY',
    '476': 'ERR_BADCHANMASK',
    #'477': 'ERR_NOCHANMODES',
    #'477': 'ERR_NEEDREGGEDNICK',
    '478': 'ERR_BANLISTFULL',
    '479': 'ERR_BADCHANNAME',
    '479': 'ERR_LINKFAIL',
    #'480': 'ERR_NOULINE',
    #'480': 'ERR_CANNOTKNOCK',
    '481': 'ERR_NOPRIVILEGES',
    '482': 'ERR_CHANOPRIVSNEEDED',
    '483': 'ERR_CANTKILLSERVER',
    #'484': 'ERR_RESTRICTED',
    #'484': 'ERR_ISCHANSERVICE',
    #'484': 'ERR_DESYNC',
    #'484': 'ERR_ATTACKDENY',
    '485': 'ERR_UNIQOPRIVSNEEDED',
    #'485': 'ERR_KILLDENY',
    #'485': 'ERR_CANTKICKADMIN',
    #'485': 'ERR_ISREALSERVICE',
    #'486': 'ERR_NONONREG',
    #'486': 'ERR_HTMDISABLED',
    #'486': 'ERR_ACCOUNTONLY',
    #'487': 'ERR_CHANTOORECENT',
    #'487': 'ERR_MSGSERVICES',
    '488': 'ERR_TSLESSCHAN',
    #'489': 'ERR_VOICENEEDED',
    #'489': 'ERR_SECUREONLYCHAN',
    '491': 'ERR_NOOPERHOST',
    #'492': 'ERR_NOSERVICEHOST',
    '493': 'ERR_NOFEATURE',
    '494': 'ERR_BADFEATURE',
    '495': 'ERR_BADLOGTYPE',
    '496': 'ERR_BADLOGSYS',
    '497': 'ERR_BADLOGVALUE',
    '498': 'ERR_ISOPERLCHAN',
    '499': 'ERR_CHANOWNPRIVNEEDED',
    '501': 'ERR_UMODEUNKNOWNFLAG',
    '502': 'ERR_USERSDONTMATCH',
    '503': 'ERR_GHOSTEDCLIENT',
    #'503': 'ERR_VWORLDWARN',
    '504': 'ERR_USERNOTONSERV',
    '511': 'ERR_SILELISTFULL',
    '512': 'ERR_TOOMANYWATCH',
    '513': 'ERR_BADPING',
    #'514': 'ERR_INVALID_ERROR',
    #'514': 'ERR_TOOMANYDCC',
    '515': 'ERR_BADEXPIRE',
    '516': 'ERR_DONTCHEAT',
    '517': 'ERR_DISABLED',
    #'518': 'ERR_NOINVITE',
    #'518': 'ERR_LONGMASK',
    #'519': 'ERR_ADMONLY',
    #'519': 'ERR_TOOMANYUSERS',
    #'520': 'ERR_OPERONLY',
    #'520': 'ERR_MASKTOOWIDE',
    #'520': 'ERR_WHOTRUNC',
    #'521': 'ERR_LISTSYNTAX',
    '522': 'ERR_WHOSYNTAX',
    '523': 'ERR_WHOLIMEXCEED',
    #'524': 'ERR_QUARANTINED',
    #'524': 'ERR_OPERSPVERIFY',
    '525': 'ERR_REMOTEPFX',
    '526': 'ERR_PFXUNROUTABLE',
    '550': 'ERR_BADHOSTMASK',
    '551': 'ERR_HOSTUNAVAIL',
    '552': 'ERR_USINGSLINE',
    #'553': 'ERR_STATSSLINE',
    '600': 'RPL_LOGON',
    '601': 'RPL_LOGOFF',
    '602': 'RPL_WATCHOFF',
    '603': 'RPL_WATCHSTAT',
    '604': 'RPL_NOWON',
    '605': 'RPL_NOWOFF',
    '606': 'RPL_WATCHLIST',
    '607': 'RPL_ENDOFWATCHLIST',
    '608': 'RPL_WATCHCLEAR',
    #'610': 'RPL_MAPMORE',
    #'610': 'RPL_ISOPER',
    '611': 'RPL_ISLOCOP',
    '612': 'RPL_ISNOTOPER',
    '613': 'RPL_ENDOFISOPER',
    #'615': 'RPL_MAPMORE',
    #'615': 'RPL_WHOISMODES',
    #'616': 'RPL_WHOISHOST',
    #'617': 'RPL_DCCSTATUS',
    #'617': 'RPL_WHOISBOT',
    '618': 'RPL_DCCLIST',
    #'619': 'RPL_ENDOFDCCLIST',
    #'619': 'RPL_WHOWASHOST',
    #'620': 'RPL_DCCINFO',
    #'620': 'RPL_RULESSTART',
    #'621': 'RPL_RULES',
    #'622': 'RPL_ENDOFRULES',
    #'623': 'RPL_MAPMORE',
    '624': 'RPL_OMOTDSTART',
    '625': 'RPL_OMOTD',
    '626': 'RPL_ENDOFO',
    '630': 'RPL_SETTINGS',
    '631': 'RPL_ENDOFSETTINGS',
    #'640': 'RPL_DUMPING',
    #'641': 'RPL_DUMPRPL',
    #'642': 'RPL_EODUMP',
    '660': 'RPL_TRACEROUTE_HOP',
    '661': 'RPL_TRACEROUTE_START',
    '662': 'RPL_MODECHANGEWARN',
    '663': 'RPL_CHANREDIR',
    '664': 'RPL_SERVMODEIS',
    '665': 'RPL_OTHERUMODEIS',
    '666': 'RPL_ENDOF_GENERIC',
    '670': 'RPL_WHOWASDETAILS',
    '671': 'RPL_WHOISSECURE',
    '672': 'RPL_UNKNOWNMODES',
    '673': 'RPL_CANNOTSETMODES',
    '678': 'RPL_LUSERSTAFF',
    '679': 'RPL_TIMEONSERVERIS',
    '682': 'RPL_NETWORKS',
    '687': 'RPL_YOURLANGUAGEIS',
    '688': 'RPL_LANGUAGE',
    '689': 'RPL_WHOISSTAFF',
    '690': 'RPL_WHOISLANGUAGE',
    '702': 'RPL_MODLIST',
    '703': 'RPL_ENDOFMODLIST',
    '704': 'RPL_HELPSTART',
    '705': 'RPL_HELPTXT',
    '706': 'RPL_ENDOFHELP',
    '708': 'RPL_ETRACEFULL',
    '709': 'RPL_ETRACE',
    '710': 'RPL_KNOCK',
    '711': 'RPL_KNOCKDLVR',
    '712': 'ERR_TOOMANYKNOCK',
    '713': 'ERR_CHANOPEN',
    '714': 'ERR_KNOCKONCHAN',
    '715': 'ERR_KNOCKDISABLED',
    '716': 'RPL_TARGUMODEG',
    '717': 'RPL_TARGNOTIFY',
    '718': 'RPL_UMODEGMSG',
    '720': 'RPL_OMOTDSTART',
    '721': 'RPL_OMOTD',
    '722': 'RPL_ENDOFOMOTD',
    '723': 'ERR_NOPRIVS',
    '724': 'RPL_TESTMARK',
    '725': 'RPL_TESTLINE',
    '726': 'RPL_NOTESTLINE',
    '771': 'RPL_XINFO',
    '773': 'RPL_XINFOSTART',
    '774': 'RPL_XINFOEND',
    '972': 'ERR_CANNOTDOCOMMAND',
    '973': 'ERR_CANNOTCHANGEUMODE',
    '974': 'ERR_CANNOTCHANGECHANMODE',
    '975': 'ERR_CANNOTCHANGESERVERMODE',
    '976': 'ERR_CANNOTSENDTONICK',
    '977': 'ERR_UNKNOWNSERVERMODE',
    '979': 'ERR_SERVERMODELOCK',
    '980': 'ERR_BADCHARENCODING',
    '981': 'ERR_TOOMANYLANGUAGES',
    '982': 'ERR_NOLANGUAGE',
    '983': 'ERR_TEXTTOOSHORT',
    '999': 'ERR_NUMERIC_ERR',
}