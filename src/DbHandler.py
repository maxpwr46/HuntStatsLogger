import sqlite3
import ctypes
from resources import *


def json_to_db(obj):
    log('inserting record into database')
    teams = obj['teams']
    hunters = obj['hunters']
    entries = obj['entries']
    game = obj['game']
    accolades = obj['accolades']
    timestamps = obj['timestamps']

    conn = sqlite3.connect(database)
    for teamnum in teams:
        insert_row(conn, "teams", teams[teamnum])
    for hunternum in hunters:
        insert_row(conn, "hunters", hunters[hunternum])
    for entrynum in entries:
        insert_row(conn, "entries", entries[entrynum])
    for accoladenum in accolades:
        insert_row(conn, "accolades", accolades[accoladenum])
    for timestampnum in timestamps:
        insert_row(conn, "timestamps", timestamps[timestampnum])
    insert_row(conn, "games", game)
    conn.close()

def add_column(table, column):
    conn = sqlite3.connect(database)
    cursor = conn.cursor()
    query = "alter table %s add column %s" % (table,column)
    log(query)
    try:
        cursor.execute(query)
        conn.commit()
    except Exception as e:
        print('add_column')
        print(e)

def insert_row(conn, table, row):
    cursor = conn.cursor()
    cols = [i for i in row.keys()]
    vals = [row[i] for i in cols]
    query = "insert or ignore into %s (%s) values (%s) " % (table, ','.join(cols), (','.join(['?']*len(cols))))
    try:
        cursor.execute(query, (vals))
        conn.commit()
    except Exception as e:
        if 'syntax error' in str(e):
            print('insert_row')
            print(e)
            problem = str(e).split("\"")[1]
            for key in row:
                if problem in key:
                    row.pop(key)
                    break
            print('\tsyntax error repaired')
            insert_row(conn, table,row)
        elif 'has no column' in str(e):
            if 'MissionBagWasDeathlessUsed' in str(e):
                add_column('games','MissionBagWasDeathlessUsed')
                insert_row(conn, table,row)
            elif 'MissionBagAddNoBloodlineXp' in str(e):
                add_column('games','MissionBagAddNoBloodlineXp')
                insert_row(conn, table, row)
            elif 'MissionBagIsTutorial' in str(e):
                add_column('games','MissionBagIsTutorial')
                insert_row(conn, table, row)
            else:
                log(e)
                log('insert_row; has no column')
        else:
            log(e)
            log('insert_row')


def tables_exist():
    conn = sqlite3.connect(database)
    cursor = conn.cursor()
    tables = ('games','hunters','entries','teams','accolades','timestamps')
    query = "select name from sqlite_master where type = 'table' and %s" % (" or ".join(["name = ?"] * len(tables)))

    try:
        cursor.execute(query,tables)
        nTables = len(cursor.fetchall())
        conn.close()
        return nTables == len(tables)
    except Exception as e:
        log('tables_exist err')
        log(e)
        conn.close()
        return False

def create_tables():
    log('creating tables')
    conn = sqlite3.connect(database)
    cursor = conn.cursor()
    cursor.executescript(open(resource_path('assets/schema.sql'),'r').read())
    conn.close()

def delete_hunt(id):
    print('delete game %s' % (id))
    tables = ['games','hunters','teams','accolades','entries','timestamps']
    queries = ["delete from %s where game_id = '%s'" % (table,id) for table in tables]
    print(queries)
    query = "; ".join(queries)
    print(query)

    conn = sqlite3.connect(database)
    cursor = conn.cursor()
    cursor.executescript('; '.join(["begin",query,"commit;"]))
    conn.commit()

def execute_query(query,opts=None):
    conn = sqlite3.connect(database)
    cursor = conn.cursor()
    try:
        if opts != None:
            cursor.execute(query,opts)
        else:
            cursor.execute(query)
        return cursor.fetchall()
    except Exception as e:
        log('execute_query err')
        log('requested query: %s' % query)
        log(e)
        return []

def GetHuntTimestamps(ts):
    id = execute_query("select game_id from 'games' where timestamp is %s" % ts)
    if len(id) == 0:
        return []
    id = id[0][0]
    cols = execute_query("pragma table_info('timestamps')")
    timestamps = execute_query("select * from 'timestamps' where game_id is '%s' order by timestamp asc" % id)
    res = []
    res = [{cols[j][1] : timestamps[i][j] for j in range(len(cols))} for i in range(len(timestamps))]
    return res
    

def GetTotalHuntCount():
    n = execute_query("select count(*) from 'games'")
    if n == None or len(n) == 0:
        return -1 
    return n[0][0]

def GetCurrentMmr(pid = None):
    if pid == None or pid < 0:
        pid = settings.value("profileid")
    mmr = execute_query("select mmr from 'hunters' where profileid is '%s' and timestamp is %d" % (pid, GetLastHuntTimestamp()))
    if len(mmr) == 0:
        return -1
    mmr = mmr[0][0]
    if mmr == None:
        return -1
    return mmr

def GetGameId(ts):
    query = "select game_id from 'games' where timestamp is '%s'" % ts
    res = execute_query(query)
    if len(res) == 0:
        return ''
    return res[0][0]

def GetBestMmr(pid = None):
    if pid == None or pid < 0:
        pid = settings.value("profileid")
    mmr = execute_query("select max(mmr) from 'hunters' where profileid is '%s'" % pid)
    if len(mmr) == 0:
        return -1
    mmr = mmr[0][0]
    if mmr == None:
        return -1
    return mmr

def GetTopKiller():
    vals = execute_query("select downedme+killedme as kills, blood_line_name, profileid, mmr from 'hunters' order by kills desc limit 1")
    cols = ['kills','name','pid','mmr']
    if len(vals) > 0:
        res = { cols[i] : vals[0][i] for i in range(len(cols))}
        return res
    return {}

def GetTopKilled():
    vals = execute_query("select downedbyme+killedbyme as kills, blood_line_name, profileid, mmr from 'hunters' order by kills desc limit 1")
    cols = ['kills','name','pid','mmr']
    if len(vals) > 0:
        res = { cols[i] : vals[0][i] for i in range(len(cols))}
        return res
    return {}

def GetTopNHunters(n):
    cols = ['frequency','name', 'profileid', 'mmr','killedme','killedbyme']
    vals = execute_query("select count(profileid) as frequency, blood_line_name, profileid, mmr, killedme+downedme as killedme, killedbyme+downedbyme as killedbyme from 'hunters' where profileid is not '%s' group by profileid order by frequency desc limit %d" % (settings.value("profileid"), n))
    #vals = execute_query("select count(profileid) as frequency, blood_line_name, profileid, mmr, killedme+downedme as killedme, killedbyme+downedbyme as killedbyme from 'hunters' group by profileid order by frequency desc limit %d" % (n))
    results = []
    if len(vals) > 0:
        for v in vals:
            results.append(
                { cols[i] : v[i] for i in range(len(cols)) }
            )
    return results

def GetHunts(earliest=0,IsQuickPlay = 'all'):
    if debug:
        print("dbHandler.GetHunts")
    if IsQuickPlay == 'all':
        vals = execute_query("select * from 'games' where timestamp > %s order by timestamp desc" % earliest)
    elif IsQuickPlay == 'true':
        vals = execute_query("select * from 'games' where timestamp > %s and MissionBagIsQuickPlay = 'true' order by timestamp desc" % earliest)
    elif IsQuickPlay == 'false':
        vals = execute_query("select * from 'games' where timestamp > %s and MissionBagIsQuickPlay = 'false' order by timestamp desc" % earliest)
    cols = execute_query("pragma table_info('games')")
    try:
        return [ { cols[i][1] : hunt[i] for i in range(len(cols)) } for hunt in vals]
    except Exception as e:
        log('dbhandler.gethunts')
        log(e)
        return []

def GetHunt(ts):
    vals = execute_query("select * from 'games' where timestamp is %d" % ts)
    cols = execute_query("pragma table_info('games')")
    try:
        vals = vals[0]
        return { cols[i][1] : vals[i] for i in range(len(cols)) }
    except Exception as e:
        log('dbhandler.gethunt')
        log(e)
        return {}

def GetLastHuntTimestamp():
    ts = execute_query("select timestamp from 'games' order by timestamp desc limit 1")
    if ts == None or len(ts) < 1:
        return -1
    return ts[0][0]

def GetHuntEntries(ts):
    vals = execute_query("select * from 'entries' where timestamp is %s" % ts) 
    cols = execute_query("pragma table_info('entries')")
    try:
        return [ { cols[i][1] : entry[i] for i in range(len(cols)) } for entry in vals]

    except Exception as e:
        log('dbhandler.getentries')
        log(e)
        return {}

def GetHuntAccolades(ts):
    vals = execute_query("select * from 'accolades' where timestamp is %s" % ts) 
    cols = execute_query("pragma table_info('accolades')")
    try:
        return [ { cols[i][1] : entry[i] for i in range(len(cols)) } for entry in vals]

    except Exception as e:
        log('dbhandler.getaccolades')
        log(e)
        return {}

def GetKillsByMatch():
        kData = execute_query("select downedbyme + killedbyme as kills, 'games'.MissionBagIsQuickPlay, 'games'.timestamp from 'hunters' join 'games' on 'hunters'.game_id = 'games'.game_id")
        cols = ["kills","isQp","ts"]
        data = []
        try:
            for k in kData:
                data.append({cols[i] : k[i] for i in range(len(cols))})
        except Exception as e:
            log('dbhandler.getkillsbymatch')
            log(e)

        res = {}
        for d in data:
            ts = d['ts']
            if ts not in res:
                res[ts] = {"isQp":d['isQp'],"kills": 0}
            res[ts]["kills"] += d["kills"]
        return res

def GetTeamKillsByMatch():
        kData = execute_query("select downedbyme + killedbyme as kills, downedbyteammate + killedbyteammate as team_kills, 'games'.timestamp from 'hunters' join 'games' on 'hunters'.game_id = 'games'.game_id where 'games'.MissionBagIsQuickPlay = 'false'")
        cols = ["kills","team_kills","ts"]
        data = []
        try:
            for k in kData:
                data.append({cols[i] : k[i] for i in range(len(cols))})
        except Exception as e:
            log('dbhandler.getkillsbymatch')
            log(e)

        res = {}
        for d in data:
            ts = d['ts']
            if ts not in res:
                res[ts] = 0
            res[ts] += d["kills"]
            res[ts] += d["team_kills"]
        return res

def GetDeathsByMatch():
        dData = execute_query("select downedme + killedme, 'games'.MissionBagIsQuickPlay, 'games'.timestamp from 'hunters' join 'games' on 'hunters'.game_id = 'games'.game_id")
        cols = ["deaths","isQp","ts"]
        data = []
        try:
            for d in dData:
                data.append({cols[i] : d[i] for i in range(len(cols))})
        except Exception as e:
            log('dbhandler.getdeathsbymatch')
            log(e)
        res = {}
        for d in data:
            ts = d['ts']
            if ts not in res:
                res[ts] = {"isQp":d['isQp'],"deaths": 0}
            res[ts]["deaths"] += d["deaths"]
        return res

def GetAssistsByMatch():
        aData = execute_query("select amount, isQp, ts from (select 'entries'.amount, MissionBagIsQuickPlay as isQp, 'games'.timestamp as ts from 'entries' join 'games' on 'games'.game_id = 'entries'.game_id where category is 'accolade_players_killed_assist')")
        cols = ["assists","isQp","ts"]
        data = []
        try:
            for a in aData:
                data.append({cols[i] : a[i] for i in range(len(cols))})
        except Exception as e:
            log('dbhandler.getassistsbymatch')
            log(e)
        res = {}
        for d in data:
            ts = d['ts']
            if ts not in res:
                res[ts] = {"isQp":d['isQp'],"assists": 0}
            res[ts]["assists"] += d["assists"]
        return res

def GetTeams(timestamp):
    tVals = execute_query("select * from 'teams' where timestamp is %s" % timestamp)
    tCols = execute_query("pragma table_info('teams')")
    teams = []
    try:
        for team in tVals:
            teams.append({tCols[i][1] : team[i] for i in range(len(tCols))})

    except Exception as e:
        log("dbhandler.getteams")
        log(e)
    return teams

def GetHunterFromGame(hunter_num,team_num,game_id):
    res = execute_query("select blood_line_name from 'hunters' where hunter_num is '%s' and team_num is '%s' and game_id is '%s'" % (hunter_num,team_num,game_id))
    if len(res) == 0:
        return ''
    return res[0][0]

def GetHunterByName(name):
    res = execute_query("select profileid from 'hunters' where blood_line_name is ? collate nocase limit 1", [name])
    if len(res) > 0:
        return GetHunterByProfileId(res[0][0])
    return []

def GetNameByProfileId(pid):
    vals = execute_query("select blood_line_name from 'hunters' where profileid is %d limit 1" % pid)
    if len(vals) > 0:
        return vals[0][0]
    return ''

def GetHunterByProfileId(pid):
    vals = execute_query("select * from 'hunters' where profileid is %d" % pid)
    cols = execute_query("pragma table_info('hunters')")
    res = []
    try:
        for v in vals:
            res.append({cols[i][1] : v[i] for i in range(len(cols))})
    except Exception as e:
        log('dbhandler.gethunterbyname')
        log(e)
    return res

def GetHunterKills(pid):
    vals = execute_query("select sum(downedme + killedme) as killedby, sum(downedbyme + killedbyme) as killed from 'hunters' where profileid is %d" % pid)
    cols = ['killedby','killed']
    res = []
    try:
        for v in vals:
            res.append({cols[i] : v[i] for i in range(len(cols))})
    except Exception as e:
        log('dbhandler.gethunterkills')
        log(e)
    return res

def GetHunters(timestamp):
    hVals = execute_query("select * from 'hunters' where timestamp is %s" % timestamp)
    hCols = execute_query("pragma table_info('hunters')")
    hunters = []
    try:
        for hunter in hVals:
            hunters.append({hCols[i][1] : hunter[i] for i in range(len(hCols))})
        return hunters
    except Exception as e:
        log('dbhandler.gethunters')
        log(e)
        return []

def GetAllMmrs(pid = settings.value('profileid')):
    vals = execute_query("select 'hunters'.timestamp, 'hunters'.mmr, 'games'.MissionBagIsQuickPlay as qp from 'hunters' join 'games' on 'hunters'.timestamp = 'games'.timestamp where profileid is '%s' order by 'hunters'.timestamp asc" % pid)
    res = {}
    for v in vals:
        res[v[0]] = {
            'mmr': v[1],
            'qp': v[2]
        }
    return res

def GetTeamMmrs():
    vals = execute_query("select timestamp, mmr from 'teams' where ownteam is 'true'")
    return {v[0] : v[1] for v in vals}

def GetGameTypes():
    earliest = 0
    timeRange = int(settings.value("kda_range","-1"))
    if timeRange > -1:
        earliest = int(time.time() - timeRange)
    cols = ['timestamp', 'MissionBagIsQuickplay']
    vals = execute_query("select %s from 'games' where timestamp > %s order by timestamp asc" % (','.join(cols),earliest))
    res = {}
    for v in vals:
        res[v[0]] = v[1]
    return res

def GetTeamGames(pids : list):
    if len(pids) <= 1 or len(pids) > 3:
        return []
    if len(pids) == 2:
        res = execute_query("select h1.timestamp from hunters h1 inner join hunters h2 on h1.profileid = '%s' and h2.profileid = '%s' and h1.timestamp = h2.timestamp and h1.team_num = h2.team_num" % (pids[0],pids[1]))
        res = [r[0] for r in res]
        return res
    if len(pids) == 3:
        res = execute_query("select h1.timestamp from hunters h1 inner join hunters h2 inner join hunters h3 on h1.profileid = '%s' and h2.profileid = '%s' and h3.profileid = '%s' and h1.timestamp = h2.timestamp and h2.timestamp = h3.timestamp and h1.team_num = h2.team_num and h3.team_num = h3.team_num" % (pids[0],pids[1],pids[2]))
        res = [r[0] for r in res]
        return res

def GetTeamMembers(ts):
    if debug:
        print("dbhandler.getTeamMembers")
    vals = execute_query(
        "select 'hunters'.profileid,'hunters'.game_id, 'hunters'.timestamp, 'teams'.team_num from 'hunters' join 'teams' on (ownteam = 'true' and 'hunters'.game_id = 'teams'.game_id and 'hunters'.team_num = 'teams'.team_num) join 'games' on ('games'.MissionBagIsQuickPlay = 'false' and 'teams'.game_id = 'games'.game_id) where 'hunters'.timestamp = %d" % ts
    )
    if len(vals) == 0:
        return {}
    res = {'pid':[],'game_id':vals[0][1],'timestamp':vals[0][2],'team_num':vals[0][3]}
    for v in vals:
        res['pid'].append(v[0])
    res['pid'] = sorted(res['pid'])
    return res

# thanks @Huakas
def predictNextMmr(currentMmr = None, currentTs = None):
    if not currentMmr:
        currentMmr = GetCurrentMmr()
    if not currentTs:
        currentTs = GetLastHuntTimestamp()
    predictedChange = 0
    your_kills = execute_query("select downedbyme+killedbyme,mmr from 'hunters' where timestamp is %d and (downedbyme > 0 or killedbyme > 0)" % currentTs)
    your_deaths = execute_query("select downedme+killedme,mmr from 'hunters' where timestamp is %d and (downedme > 0 or killedme > 0)" % currentTs)

    for hunter in your_kills:
        kills = hunter[0]
        mmr = hunter[1]
        mmrValue = min(15, (currentMmr - mmr) / 25)
        predictedChange += (15 - mmrValue) * kills
    for hunter in your_deaths:
        deaths = hunter[0]
        mmr = hunter[1]
        mmrValue = max(-15, (currentMmr - mmr) / 25)
        predictedChange += (-15 - mmrValue) * deaths

    return currentMmr + predictedChange

def getAssists(ts):
    entries = GetHuntEntries(ts)
    assists = 0
    for entry in entries:
        cat = entry['category']
        if 'players_killed' in cat:
            if 'assist' in cat:
                assists += entry['amount']
    return assists


# GetTopHunts functions:
def getHuntsSortByKillCount(ts = -1, num = -1, isQp='all'):
    if isQp == 'false':
        condition = "and 'games'.MissionBagIsQuickPlay is 'false'" 
    elif isQp == 'true':
        condition = "and 'games'.MissionBagIsQuickPlay is 'true'" 
    else:
        condition = ""

    cols = execute_query("pragma table_info('games')")
    cols = [c[1] for c in cols]
    cols.append('your_kills')
    vals = execute_query("select 'games'.*, sum(downedbyme+killedbyme) as kills from 'hunters' join 'games' on 'hunters'.timestamp = 'games'.timestamp where 'games'.timestamp > %s %s group by 'hunters'.timestamp order by kills desc %s" % (ts, condition, "limit %d" % num if num > 0 else ""))
    res = []
    for v in vals:
        res.append({cols[i] : v[i] for i in range(len(cols))})
    return res

def getHuntsSortByDeathCount(ts=-1, num=-1, isQp='all'):
    if isQp == 'false':
        condition = "and 'games'.MissionBagIsQuickPlay is 'false'" 
    elif isQp == 'true':
        condition = "and 'games'.MissionBagIsQuickPlay is 'true'" 
    else:
        condition = ""

    cols = execute_query("pragma table_info('games')")
    cols = [c[1] for c in cols]
    cols.append('your_deaths')
    vals = execute_query("select 'games'.*, sum(downedme+killedme) as deaths from 'hunters' join 'games' on 'hunters'.timestamp = 'games'.timestamp where 'games'.timestamp > %s %s group by 'hunters'.timestamp order by deaths desc %s" % (ts, condition, "limit %d" % num if num > 0 else ""))
    res = []
    for v in vals:
        res.append({cols[i] : v[i] for i in range(len(cols))})
    return res

def getHuntsSortByTeamKillCount(ts = -1, num = -1, isQp='all'):
    if isQp == 'false':
        condition = "and 'games'.MissionBagIsQuickPlay is 'false'" 
    elif isQp == 'true':
        condition = "and 'games'.MissionBagIsQuickPlay is 'true'" 
    else:
        condition = ""

    cols = execute_query("pragma table_info('games')")
    cols = [c[1] for c in cols]
    cols.append('team_kills')
    vals = execute_query("select 'games'.*, sum(downedbyme+killedbyme+downedbyteammate+killedbyteammate) as kills from 'hunters' join 'games' on 'hunters'.timestamp = 'games'.timestamp where 'games'.timestamp > %s %s group by 'hunters'.timestamp order by kills desc %s" % (ts, condition, "limit %d" % num if num > 0 else ""))
    res = []
    for v in vals:
        res.append({cols[i] : v[i] for i in range(len(cols))})
    return res

def getTimestampsSortByMaxTimestamp(ts=-1,num=-1,isQp='all'):
    if isQp == 'false':
        condition = "and 'games'.MissionBagIsQuickPlay is 'false'" 
    elif isQp == 'true':
        condition = "and 'games'.MissionBagIsQuickPlay is 'true'" 
    else:
        condition = ""

    cols = execute_query("pragma table_info('games')")
    cols = [c[1] for c in cols]
    cols.append('duration')
    vals = execute_query("SELECT 'games'.*, max('timestamps'.timestamp) as duration FROM 'timestamps' join 'games' on 'timestamps'.game_id = 'games'.game_id where 'games'.timestamp > %s %s group by 'timestamps'.game_id order by 'timestamps'.timestamp desc %s" % (ts, condition, "limit %d" % num if num > 0 else ""))
    res = []
    for v in vals:
        res.append({cols[i] : v[i] for i in range(len(cols))})
    return res


def getHuntsSortByAssistCount(ts=-1, num=-1, isQp='all'):
    if isQp == 'false':
        condition = "and 'games'.MissionBagIsQuickPlay is 'false'" 
    elif isQp == 'true':
        condition = "and 'games'.MissionBagIsQuickPlay is 'true'" 
    else:
        condition = ""

    cols = execute_query("pragma table_info('games')")
    cols = [c[1] for c in cols]
    cols.append('assists')
    vals = execute_query("SELECT 'games'.*, 'entries'.amount FROM 'entries' join 'games' on 'entries'.timestamp = 'games'.timestamp where category like '%%assist%%' and 'games'.timestamp > %s %s order by amount desc %s" %(ts, condition, "limit %d" % num if num > 0 else ""))
    res = []
    for v in vals:
        res.append({cols[i] : v[i] for i in range(len(cols))})
    return res



def getYourKillCount(ts, max = -1):
    if max > 0:
        vals = execute_query(
            "select downedbyme+killedbyme as killedbyme from 'hunters' where timestamp is %d and (downedbyme > 0 or killedbyme > 0) limit %d" % (ts, max)
        )
    else:
        vals = execute_query(
            "select downedbyme+killedbyme as killedbyme from 'hunters' where timestamp is %d and (downedbyme > 0 or killedbyme > 0)" % (ts)
        )
    return sum(sum(i) for i in vals)

def getYourDeathCount(ts):
    vals = execute_query(
        "select downedme+killedme as deaths from 'hunters' where timestamp is %d and (downedme > 0 or killedme > 0)" % ts
    )
    return sum(sum(i) for i in vals)

def getTeamKillCount(ts):
    vals = execute_query(
        "select downedbyteammate+killedbyteammate as killedbyteammate, downedbyme+killedbyme as killedbyme from 'hunters' where timestamp is %d and ((downedbyteammate > 0 or killedbyteammate > 0) or (downedbyme > 0 or killedbyme > 0))" % ts
    )
    return sum(sum(i) for i in vals)

def getKillData(ts):
    your_kills = {i+1: 0 for i in range(6)}
    your_deaths = {i+1: 0 for i in range(6)}
    team_kills = {i+1: 0 for i in range(6)}

    cols = ["killedbyme","killedme","killedbyteammate","mmr"]
    selection = "downedbyme+killedbyme as killedbyme,downedme+killedme as killedme,downedbyteammate+killedbyteammate as killedbyteammate, mmr"
    condition = "timestamp is %d and ((downedbyme > 0 or killedbyme > 0) or (downedme > 0 or killedme > 0) or (downedbyteammate > 0 or killedbyteammate > 0))" % ts
    vals = execute_query(
        "select %s from 'hunters' where %s" % (selection, condition)
    )
    all_kills = []
    for v in vals:
        all_kills.append({cols[i] : v[i] for i in range(len(cols))})

    for k in all_kills:
        mmr = mmr_to_stars(k['mmr'])
        your_kills[mmr] += k['killedbyme']
        team_kills[mmr] += k['killedbyme']
        team_kills[mmr] += k['killedbyteammate']
        your_deaths[mmr] += k['killedme']

    assists = getAssists(ts)
    return {
        "your_kills": your_kills,
        "team_kills": team_kills,
        "your_deaths": your_deaths,
        "assists": assists
    }


def SameTeamCount(name):
    res = execute_query("select count(*) from 'hunters' join 'teams' on 'teams'.ownteam = 'true' and 'hunters'.team_num = 'teams'.team_num and 'hunters'.timestamp = 'teams'.timestamp where 'hunters'.blood_line_name = '%s'" % name)
    res = 0 if len(res) == 0 else res[0][0]
    return res

def getAllUsernames(pid):
    allnamesarray = execute_query(
        "select blood_line_name from 'hunters' where profileid is %d group by blood_line_name" % pid)
    allnames = []
    if len(allnamesarray) <= 0:
        return allnames
    for n in allnamesarray:
        allnames.append(n[0])
    return allnames