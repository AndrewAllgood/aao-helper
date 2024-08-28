# AAO Helper

Bot of utility functions for the Axis & Allies 1942 Online community Discord server. Originally designed by Andrew, I (AirDolphin98) have rebuilt it with various new features. 

Donate to the authors:

https://ko-fi.com/aallgood

https://ko-fi.com/airdolphin98

## Overview

So far, these are the main functions of the bot:

* Roll for sides (assign players to either Axis or Allies)

* Move showcase channels and galleries between archive and main categories

* Create and edit embed messages

* After inactivity, automatically unhide threads or archive forum posts

* System that lets people give themselves Exhibition Match role

* System for granting leaderboard rank badges, storing them in a database, and updating with the ranked seasons. This is the most sophisticated functionality.

* Commands that streamline the posting of typical Hall of Fame embeds and auto-managing the awarded roles to some extent

The bot automates much of these processes and allows people who don't have perms such as manage channels/threads/roles to perform these actions.

## Setup

I have set this up on a Pebblehost server. It's cheap and decent for bot hosting (as of 2024). You can link it to a GitHub repo and have it update the code upon every server restart. Note: the actual repo linked to my host currently is combined with other bots; I copy-paste files between that and the standalone aao-helper repo.

The main file which you run the program with is `aao_helper.py`

You also need to do the following:

* If not already, invite the bot to the Discord server through the Discord developer portal, making sure it has a lot of permissions (or admin perms, but that's risky).

* Hoist the bot's Discord role above most other roles so it is allowed to operate on them.

* Create a file simply called `.env` in the bot hosting server (e.g. Pebblehost) on the same level as `aao_helper.py`. Copy the Discord bot token into this file right after this text, which is all you need: `DISCORD_BOT_TOKEN=`

* Start the bot in the host server. In Pebblehost you'll have a loader script you can run `aao_helper.py` with whenever the server starts.

* When the bot first enters a Discord server or when its commands are updated in terms of the interface (command names, descriptions, and parameters, not function code), you must type `/sync` in any Discord channel as someone with Manage Server perms to register the commands.

Setting the DEBUG variable in `params.py` to `True` allows you to test the bot with different channels and roles etc. The current debug values are for the Discord server A&AO Test Server.

## How to use

The commands for roll sides and create/edit embed should be fairly self-explanatory.

1. `/sides`

2. `/create_embed`

3. `Message right-click -> Apps -> Edit embed` (context menu command)

### Toggle showcase

4. `/toggle_showcase` Invoke this in a showcase channel to automatically move it either from its usual category to the CACHE category, or vice versa. Its gallery channel will be moved along with it. The channel order may need to be adjusted for presentation, but Discord does a decent job of preserving the order sometimes.

Note: Finals channels are often intended to have gallery-1 channels as their gallery, but only showcase-1 channels are linked to them. Therefore, you're not supposed to archive a showcase-1 channel when a finals channel is on display.

### Auto manage threads

5. `/auto_unarchive` Invoke this in a thread to automatically unhide it when it would normally disappear from the channel list after the auto archive duration. Invoke in a channel to do this for all threads in that channel. Closed/locked threads will not be affected; auto archive does not register as archiving, it somehow only changes visibility.

6. `/auto_close_forum_posts` Invoke this with a forum ID to have it automatically archive forum posts that have not had recent messages. Default cutoff is 14 days ago. Can also auto-lock if desired.

### Exhibition match

7. `/init_exhibitions` Invoke this anywhere to send embeds to all the "exhibition match" channels with a permanent button that prompts the user to enter user pings, which assigns them Exhibition Match role and reserves the channel for them until the match is ended.

8. `/end_exhibitions` A player in an exhibition match invokes this in an ongoing match channel to end the match in that channel. 

## Ranked badge system

9. `On rank react`

10. `/grant_rank`

11. `User right-click -> Apps -> Bestow Top 10`

12. `/get_season_end`

13. `/set_season_end`

14. `/show_user_ranks`

15. `/upload_user_ranks`

## Hall of fame embeds

16. `hall_of_fame` This command group allows Staff to more easily post in "hall of fame" channel. These commands grant Hall of Fame role to all featured players. 

    a. `top_10` Posts Top 10 Platinum embed for season end. If not for a just-ended season, it does not auto-grant ranks aside from Hall of Fame. 

    b. `tournament` Posts Tournament embed for Solos, Duos, or Blitz winners and finalists. The primary Champion roles are not managed by this, but the underlying Champions role is. Blitz tournament follows a dethrone policy as of 2024, so remember to manually remove the previous Blitz Champion's role, and the underlying Champion role if not champion in another tournament.

    c. `league` Posts League Generals embed. Provides the option to cycle the Generals and Supreme Commander roles to the featured players, removing from other players. Choose this if for the current started League season.