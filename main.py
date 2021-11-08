import json
import csv
from rauth import OAuth2Service

BASE_URL = "https://classic.warcraftlogs.com"
TOKEN_URL = f"{BASE_URL}/oauth/token"
API_URL = f"{BASE_URL}/api/v2/client"


def main():

    # set true for test mode
    test_mode = False

    oauth_file = open("../auth/oauth2_client_info.json")
    oauth_info = json.load(oauth_file)

    CLIENT_ID = oauth_info["client_id"]
    CLIENT_SECRET = oauth_info["client_secret"]

    warcraftlogs = OAuth2Service(
        client_id=CLIENT_ID,
        client_secret=CLIENT_SECRET,
        name="warcraftlogs",
        access_token_url=TOKEN_URL,
        base_url=API_URL
    )

    data = {"grant_type": "client_credentials"}

    session = warcraftlogs.get_auth_session(data=data, decoder=json.loads)

    # guild ID or report ID are necessary to specify a certain log
    guild_id = ""
    report_id = ""

    # create menu
    # if I want to automatically get the most recent log, let me do that, otherwise, let me throw in custom information
    custom_selector = False
    while custom_selector is False:
        custom_report = input("Would you like an automatic report for the most recent log? (y/n) ")

        if custom_report == "y":
            guild_id = str(input("Guild ID (visible in your guild's wcl url, e.g. warcraftlogs.com/guild/id/######): "))
            custom_selector = True
        elif custom_report == "n":
            report_id = str(input("Report ID (visible on your wcl report url, e.g. warcraftlogs.com/reports/################): "))
            custom_selector = True
        elif custom_report == 0:
            exit(0)
        else:
            print("Invalid response. Try again, or enter 0 to exit.")

    # if user wants an automatic report, we need to get the report for them
    if report_id == "":
        # query returns the N=1 most recent report for the guild_id
        query = """query {
            reportData {
                reports(guildID: %s, limit: 1) {
                    data {
                        code
                        endTime
                    }
                }
            }
        }
        """ % guild_id
        # store the api response
        response = session.post(API_URL, json={'query': query})
        # parse the response
        response_object = json.loads(response.text)
        # then grab the report id from it
        report_id = str(response_object["data"]["reportData"]["reports"]["data"][0]["code"])
        # test to make sure we're getting the right ID
        if test_mode is True:
            print(report_id)
            print(type(report_id))

    # now that we have the report, we need to look at the fights within
    # this query returns all fight IDs
    query = """query {
        reportData {
            report(code: "%s") {
                fights {
                    id,
                    startTime,
                    endTime
                }
            }
        }
    }
    """ % report_id
    # store the api response
    response = session.post(API_URL, json={'query': query})
    # parse the response
    fight_ids = json.loads(response.text)
    # test the parse was successful
    if test_mode is True:
        print(fight_ids)

    # we also need the player IDs
    # this query returns all the player actors found in the report
    query = """query {
        reportData {
            report(code: "%s") {
                masterData{
                    actors(type: "player"){
                        name,
                        id
                    }
                }
            }
        }
    }
    """ % report_id
    # store the api response
    response = session.post(API_URL, json={'query': query})
    # parse the response
    player_ids = json.loads(response.text)

    # now, we will need to add up all of the time within the raid that was spent in an encounter
    # to do that, we want to iterate through each fight and add up the difference between their endTime and startTime
    combat_time = 0
    fight_iterator = 0
    # we will add a sneaky endTime grabber here for later, as knowing when the raid ends will be important
    raid_end = 0
    for i in fight_ids["data"]["reportData"]["report"]["fights"]:
        start_time = int(fight_ids["data"]["reportData"]["report"]["fights"][fight_iterator]["startTime"])
        end_time = int(fight_ids["data"]["reportData"]["report"]["fights"][fight_iterator]["endTime"])
        raid_end = end_time
        fight_time = end_time - start_time
        combat_time += fight_time
        fight_iterator += 1
        # test to see if this is adding up time
        if test_mode is True:
            print(combat_time)

    # now that we have most of the API information we need, we need to consider which buffs we care about
    # we will open a csv file containing the buffs we care about and their information
    buff_file = open("../consumables/consumables.csv", 'r', encoding='utf-8')
    # first we load the csv
    reader = csv.DictReader(buff_file)
    # then write these to an json object, row by row
    buffs = []
    for row in reader:
        buffs.append(row)
    # now dump these into json format
    buffs = json.loads(json.dumps(buffs))
    # test buffs to make sure it looks like the json object we're expecting
    if test_mode is True:
        print(buffs)

    # now we just need to check our players buffs against the buffs we care about
    # before we do that, we need a dictionary to hold buff information
    # auras = [{"auraName", "guid", "totalUptime", "activeFlag", "consumableName", "consumableID"}]
    auras = [{}]
    # since we want a nice square table at the end, we can prefill a lot of this information, knowing some will have 0 uptime
    auras_iterator = 0
    for i in buffs:
        temp_info = {"auraName": buffs[auras_iterator]["spell_name"],
                     "guid": buffs[auras_iterator]["spell_id"],
                     "consumableName": buffs[auras_iterator]["consumable_name"],
                     "consumableID": buffs[auras_iterator]["item_id"],
                     "totalUptime": 0,
                     "activeFlag": False}
        auras.append(temp_info)

        # the following is commented out for posterity, this was an alternative way to achieve the same effect -I BELIEVE-
        # auras[auras_iterator]["auraName"] = buffs[auras_iterator]["spell_name"]
        # auras[auras_iterator]["guid"] = buffs[auras_iterator]["spell_id"]
        # auras[auras_iterator]["consumableName"] = buffs[auras_iterator]["consumable_name"]
        # auras[auras_iterator]["consumableID"] = buffs[auras_iterator]["item_id"]
        # auras[auras_iterator]["totalUptime"] = 0
        # auras[auras_iterator]["activeFlag"] = False

        auras_iterator += 1
    # the list has no initial values, so the first element is empty, pop it off
    auras.pop(0)

    # test print auras to make sure it looks right
    if test_mode is True:
        temp_iterator = 0
        for i in auras:
            print(auras[temp_iterator]["guid"])
            temp_iterator += 1

    # now that's settled, we also need a dictionary to identify players, where we will nest auras
    players = [{}]

    # now, we should populate it for each player
    # we need a variable to iterate through each player and each fight
    player_iterator = 0
    for i in player_ids["data"]["reportData"]["report"]["masterData"]["actors"]:
        # for each player, we need to query the api to find their buffs
        # to do that, we need their unique player ID, we'll store their name as well
        player_name = player_ids["data"]["reportData"]["report"]["masterData"]["actors"][player_iterator]["name"]
        player_id = player_ids["data"]["reportData"]["report"]["masterData"]["actors"][player_iterator]["id"]
        # test this player's name and id
        if test_mode is True:
            print(player_name)
            print(player_id)
        # this query reports all buffs for a given target, within a given time frame, from a given report
        query = """query {
            reportData {
                report(code: "%s") {
                    table(dataType: Buffs, startTime: 0, endTime: %s, targetID: %s) 
                }
           }
       }
       """ % (report_id, raid_end, player_id)
        # store the api response
        response = session.post(API_URL, json={'query': query})
        # test the response
        if test_mode is True:
            print(response.text)
        # parse the response
        player_buff_info = json.loads(response.text)
        # parse that down to auras
        player_auras = player_buff_info["data"]["reportData"]["report"]["table"]["data"]["auras"]
        # test print this player's auras
        if test_mode is True:
            temp_iterator = 0
            for i in player_auras:
                print(player_auras[temp_iterator])
                temp_iterator += 1

        # now that we have all the buff info, we need to look only at the uptime for auras we're interested in
        buff_iterator = 0
        for i in auras:
            # we don't want to write any erroneous data, so let's set totalUptime back to 0 and activeFlag back to false for each iteration
            auras[buff_iterator]["totalUptime"] = 0
            auras[buff_iterator]["activeFlag"] = False

            # we want to search our player's auras (from the log) for the auras we care about, so grab that spell id to search against
            search_aura = int(auras[buff_iterator]["guid"])
            # test search aura to make sure we're searching for something
            if test_mode is True:
                print(search_aura)
            # test to make sure I'm not sending any false true flags
            if test_mode is True:
                print(bool(list(filter(lambda x: x["guid"] == search_aura, player_auras))))

            if list(filter(lambda x: x["guid"] == search_aura, player_auras)):
                auras[buff_iterator]["totalUptime"] = float(list(filter(lambda x: x["guid"] == search_aura, player_auras))[0]["totalUptime"])/float(combat_time)
                auras[buff_iterator]["activeFlag"] = True
            buff_iterator += 1

        # now that we've updated all the relevant information in auras, we can toss that into our player dictionary
        # first, we want to write that list into a json object
        auras_json = json.loads(json.dumps(auras))
        # then we need a temp list to hold our information
        player_info = {"name": player_name, "id": player_id, "auras": auras_json}
        # then we need to append that onto our player list
        players.append(player_info)
        player_iterator += 1

    # now that we've iterated through all of our players, we should have all the relevant information in a dictionary
    # given the same method of populating players as auras, we need to pop the first, empty players element
    players.pop(0)
    # then, we should write that list into a json object
    players = json.loads(json.dumps(players))

    # test print players to be sure we're getting accurate data
    if test_mode is True:
        temp_iterator = 0
        for i in players:
            print(players[temp_iterator])
            temp_iterator += 1

    # printing players will print in json format
    chosen = False
    while chosen is not True:
        print_choice = input("In what format would you like this printed? (json or csv) ")
        if print_choice == "json":
            # players is already a json object, simply print it
            print(players)
            # we can also dump it to a json file
            json_file = open("../consumables/consumable_uptime_json.json", "w", encoding="utf-8")
            json.dump(players, json_file, ensure_ascii=False, indent=4)
            json_file.close()
            # chosen = True
        elif print_choice == "csv":
            # since we have nested json objects, we want to print only the data we need
            # player name, and consumable names will be the headers, first column will be player names, the rest will be uptimes
            players_csv = []
            # initiate the header string
            # interate through auras to create a list of consumable names
            header_array = ["Player Name"]
            temp_iterator = 0
            for i in players[0]["auras"]:
                header_array.append(players[0]["auras"][temp_iterator]["consumableName"])
                temp_iterator += 1
            # combine that array into one csv string
            temp_header = ",".join(header_array)
            # then append it to the total csv
            players_csv.append(temp_header)

            #now, we can loop through all players
            player_iterator = 0
            for i in players:
                entry_array = []
                entry_array.append(players[player_iterator]["name"])
                # now, loop through their consumables
                consumable_iterator = 0
                for j in players[player_iterator]["auras"]:
                    # and append their consumable uptime (consumables are always in the same order, no need to check
                    entry_array.append(str(players[player_iterator]["auras"][consumable_iterator]["totalUptime"]))
                    consumable_iterator += 1
                # now that we have their name and all consumable uptime, join that into one string
                temp_consumables = ",".join(entry_array)
                # then append it to the total csv
                players_csv.append(temp_consumables)
                player_iterator += 1

            # all players and their consumable uptimes should now be present for printing
            # we will also create/overwrite an existing consumable uptime file at the same time
            csv_file = open("../consumables/consumable_uptime_csv.csv", "w", encoding="utf-8")
            print_iterator = 0
            for i in players_csv:
                print(players_csv[print_iterator])
                csv_file.write(players_csv[print_iterator] + '\n')
                print_iterator += 1
            csv_file.close()
            print("This data was also written to ../consumables/consumable_uptime.csv")
            # chosen = True
        elif print_choice == "0":
            exit(0)
        else:
            print("Invalid selection. Try again, or enter 0 to exit.")



main()
