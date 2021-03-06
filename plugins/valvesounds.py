import json
import urllib

from cloudbot import hook
from cloudbot.util import http, web


def get_sound_info(game, search):
    search = search.replace(" ", "+")
    try:
        data = http.get_json("http://p2sounds.blha303.com.au/search/%s/%s?format=json" % (game, search))
    except urllib.error.HTTPError as e:
        return "Error: " + json.loads(e.read())["error"]
    items = []
    for item in data["items"]:
        if "music" in game:
            textsplit = item["text"].split('"')
            text = ""
            for i in range(len(textsplit)):
                if i % 2 != 0 and i < 6:
                    if text:
                        text += " / " + textsplit[i]
                    else:
                        text = textsplit[i]
        else:
            text = item["text"]
        items.append("{} - {} {}".format(item["who"],
                                         text if len(text) < 325 else text[:325] + "...",
                                         item["listen"]))
    if len(items) == 1:
        return items[0]
    else:
        return "{} (and {} others: {})".format(items[0], len(items) - 1, web.paste("\n".join(items)))


@hook.command()
def portal2(text):
    """portal2 <quote> - Look up Portal 2 quote. Example: .portal2 demand to see life's manager"""
    return get_sound_info("portal2", text)


@hook.command()
def portal2dlc(text):
    """portal2dlc <quote> - Look up Portal 2 DLC quote. Example: .portal2dlc1 these exhibits are interactive"""
    return get_sound_info("portal2dlc1", text)


@hook.command("portal2dlc2", "portal2pti")
def portal2dlc2(text):
    """portal2dlc2 <quote> - Look up Portal 2 Perpetual Testing Inititive quote. Example: .portal2 Cave here."""
    return get_sound_info("portal2dlc2", text)


@hook.command()
def portal2music(text):
    """portal2music <title> - Look up Portal 2 music. Example: .portal2music turret opera"""
    return get_sound_info("portal2music", text)


@hook.command("portal", "portal1")
def portal(text):
    """portal <quote> - Look up Portal quote. Example: .portal The last thing you want to do is hurt me"""
    return get_sound_info("portal1", text)


@hook.command("portalmusic", "portal1music")
def portalmusic(text):
    """portalmusic <title> - Look up Portal music. Example: .portalmusic still alive"""
    return get_sound_info("portal1music", text)


@hook.command("tf2sound", "tf2")
def tf2(text):
    """tf2 [who - ]<quote> - Look up TF2 quote. Example: .tf2 may i borrow your earpiece"""
    return get_sound_info("tf2", text)


@hook.command()
def tf2music(text):
    """tf2music title - Look up TF2 music lyrics. Example: .tf2music rocket jump waltz"""
    return get_sound_info("tf2music", text)
