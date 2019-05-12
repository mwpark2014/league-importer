CREATE TABLE IF NOT EXISTS accounts (
	account_id VARCHAR(64) UNIQUE NOT NULL,
    summoner_nme VARCHAR(64),
    summoner_id VARCHAR(64),
    region VARCHAR(5),
    primary key(account_id)
);

CREATE TABLE IF NOT EXISTS matches (
	match_id BIGINT UNIQUE NOT NULL,
    region VARCHAR(5),
	game_creation TIMESTAMP,
    game_duration TIMESTAMP,
    season_id TINYINT,
    game_version VARCHAR(32),
	created TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (match_id)
);

CREATE TABLE IF NOT EXISTS match_teams (
	match_team_id TINYINT NOT NULL,
    match_id BIGINT NOT NULL,
    win VARCHAR(8),
    first_blood BOOLEAN,
    first_tower BOOLEAN,
    first_inhibitor BOOLEAN,
    first_baron BOOLEAN,
    first_dragon BOOLEAN,
    first_riftherald BOOLEAN,
    tower_kills TINYINT,
    inhibitor_kills TINYINT,
    baron_kills TINYINT,
    dragon_kills TINYINT,
    riftherald_kills TINYINT,
	created TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (match_id, match_team_id),
    FOREIGN KEY	(match_id) 
		REFERENCES matches(match_id)
);

CREATE TABLE IF NOT EXISTS match_participants (
	match_participant_id TINYINT NOT NULL,
    match_team_id TINYINT NOT NULL,
    match_id BIGINT NOT NULL,
    champion_id INT NOT NULL,
    spell1_id INT NOT NULL,
    spell2_id INT NOT NULL,
    account_id VARCHAR(64) NOT NULL,
    highest_achieved_season_tier VARCHAR(16),
	win BOOLEAN,
	item0 INT,
	item1 INT,
	item2 INT,
	item3 INT,
	item4 INT,
	item5 INT,
	item6 INT, # trinket slot
	kills TINYINT,
	deaths TINYINT,
	assists TINYINT,
	largestKillingSpree TINYINT,
	largestMultiKill TINYINT,
	killingSprees TINYINT,
	longestTimeSpentLiving SMALLINT,
	doubleKills TINYINT,
	tripleKills TINYINT,
	quadraKills TINYINT,
	pentaKills TINYINT,
	unrealKills TINYINT,
	totalDamageDealt INT,
	magicDamageDealt INT,
	physicalDamageDealt INT,
	trueDamageDealt INT,
	largestCriticalStrike SMALLINT,
	totalDamageDealtToChampions INT,
	magicDamageDealtToChampions INT,
	physicalDamageDealtToChampions INT,
	trueDamageDealtToChampions INT,
	totalHeal INT,
	totalUnitsHealed SMALLINT,
	damageSelfMitigated INT,
	damageDealtToObjectives INT,
	damageDealtToTurrets SMALLINT,
	visionScore TINYINT,
	timeCCingOthers SMALLINT,
	totalDamageTaken INT,
	magicalDamageTaken INT,
	physicalDamageTaken INT,
	trueDamageTaken INT,
	goldEarned INT,
	goldSpent INT,
	turretKills TINYINT,
	inhibitorKills TINYINT,
	totalMinionsKilled SMALLINT,
	neutralMinionsKilled SMALLINT,
	totalTimeCrowdControlDealt SMALLINT,
	champLevel TINYINT,
	visionWardsBoughtInGame TINYINT,
	sightWardsBoughtInGame TINYINT,
	firstBloodKill BOOLEAN,
	firstBloodAssist BOOLEAN,
	firstTowerKill BOOLEAN,
	firstTowerAssist BOOLEAN,
	firstInhibitorKill BOOLEAN,
	firstInhibitorAssist BOOLEAN,
	created TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (match_id, match_participant_id),
	FOREIGN KEY	(match_id) 
		REFERENCES matches(match_id),
	FOREIGN KEY (match_id, match_team_id)
		REFERENCES match_teams(match_id, match_team_id),
	FOREIGN KEY	(spell1_id) 
		REFERENCES summoner_spells(ss_id),
	FOREIGN KEY	(spell2_id) 
		REFERENCES summoner_spells(ss_id),
	FOREIGN KEY	(account_id) 
		REFERENCES accounts(account_id),
	FOREIGN KEY	(item0) 
		REFERENCES items(item_id),
	FOREIGN KEY	(item1) 
		REFERENCES items(item_id),
	FOREIGN KEY	(item2) 
		REFERENCES items(item_id),
	FOREIGN KEY	(item3) 
		REFERENCES items(item_id),
	FOREIGN KEY	(item4) 
		REFERENCES items(item_id),
	FOREIGN KEY	(item5) 
		REFERENCES items(item_id),
	FOREIGN KEY	(item6) 
		REFERENCES items(item_id)
);

CREATE TABLE IF NOT EXISTS match_timeline_stats (
	match_timeline_id INT UNIQUE NOT NULL,
	match_participant_id TINYINT NOT NULL,
    match_id BIGINT NOT NULL,
    interval_0_10 FLOAT(7, 3),
    interval_10_20 FLOAT(7, 3),
    interval_20_30 FLOAT(7, 3),
    interval_30_end FLOAT(7, 3),
    PRIMARY KEY (match_timeline_id),
	FOREIGN KEY	(match_id, match_participant_id) 
		REFERENCES match_participants(match_id, match_participant_id)
);

