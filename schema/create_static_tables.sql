CREATE TABLE IF NOT EXISTS champions (
	champion_id INT UNIQUE NOT NULL, 
    patch_ver VARCHAR(10),
    name VARCHAR(20),
    title VARCHAR(50),
    blurb VARCHAR(255),
    info_attack TINYINT,
    info_defense TINYINT,
    info_magic TINYINT,
    info_difficulty TINYINT,
    resource_type VARCHAR(20),
    stat_hp FLOAT(6,3),
    stat_hpperlevel FLOAT(5,3), 
    stat_mp FLOAT(6,3),
    stat_mpperlevel FLOAT(5,3),
    stat_movespeed TINYINT,
    stat_armor FLOAT(4,2),
    stat_armorperlevel FLOAT(4,2),
    stat_spellblock FLOAT(5,3),
    stat_spellblockperlevel FLOAT(5,3),
    stat_attackrange TINYINT,
    stat_hpregen FLOAT(5,3),
    stat_hpregenperlevel FLOAT(5,3),
    stat_mpregen FLOAT(5,3),
    stat_mpregenperlevel FLOAT(5,3),
    stat_crit FLOAT(5,3),
    stat_critperlevel FLOAT(5,3),
    stat_attackdamage FLOAT(5,3),
    stack_attackdamageperlevel FLOAT(5,3),
    stat_attackspeedperlevel FLOAT(5,3),
    stat_attackspeed FLOAT(5,3),
	created TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
	last_updated TIMESTAMP NOT NULL ON UPDATE CURRENT_TIMESTAMP,
    is_active BOOLEAN,
    PRIMARY KEY (champion_id)
);

CREATE TABLE IF NOT EXISTS items (
    item_id INT UNIQUE NOT NULL,
    name VARCHAR(125),
    description VARCHAR(255),
    gold_base INT,
    gold_total INT,
    purchaseable BOOLEAN,
    active_in_srmap BOOLEAN,
    depth TINYINT,
    created TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
	last_updated TIMESTAMP NOT NULL ON UPDATE CURRENT_TIMESTAMP,
    patch_ver VARCHAR(10),
    is_active BOOLEAN,
    PRIMARY KEY (item_id)
);

CREATE TABLE IF NOT EXISTS item_item_map (
    component_id INT,
    result_id INT,
	created TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
	last_updated TIMESTAMP NOT NULL ON UPDATE CURRENT_TIMESTAMP,
    patch_ver VARCHAR(10),
    is_active BOOLEAN,
    PRIMARY KEY (component_id, result_id),
    FOREIGN KEY (component_id)
      REFERENCES items(item_id),
	FOREIGN KEY (result_id)
	  REFERENCES items(item_id)
);

CREATE TABLE IF NOT EXISTS stats (
    stat_id TINYINT,
    name VARCHAR(125),
    PRIMARY KEY (stat_id)
);

CREATE TABLE IF NOT EXISTS item_stat_map (
    item_id INT,
    stat_id TINYINT,
    value FLOAT(6,3),
    created TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
	last_updated TIMESTAMP NOT NULL ON UPDATE CURRENT_TIMESTAMP,
    patch_ver VARCHAR(10),
    is_active BOOLEAN,
    PRIMARY KEY (item_id, stat_id),
    FOREIGN KEY (item_id)
      REFERENCES items(item_id),
	FOREIGN KEY (stat_id)
	  REFERENCES stats(stat_id)
);

CREATE TABLE IF NOT EXISTS tags (
    tag_id TINYINT AUTO_INCREMENT,
    name VARCHAR(20),
    PRIMARY KEY (tag_id)
);

CREATE TABLE IF NOT EXISTS champion_tag_map (
	champion_id INT, 
    tag_id TINYINT,
	created TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
	last_updated TIMESTAMP NOT NULL ON UPDATE CURRENT_TIMESTAMP,
    patch_ver VARCHAR(10),
    is_active BOOLEAN,
    PRIMARY KEY (champion_id, tag_id),
	FOREIGN KEY (champion_id)
      REFERENCES champions(champion_id),
	FOREIGN KEY (tag_id)
	  REFERENCES tags(tag_id)
);

CREATE TABLE IF NOT EXISTS item_tag_map (
	item_id INT, 
    tag_id TINYINT,
	created TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
	last_updated TIMESTAMP NOT NULL ON UPDATE CURRENT_TIMESTAMP,
    patch_ver VARCHAR(10),
    is_active BOOLEAN,
    PRIMARY KEY (item_id, tag_id),
	FOREIGN KEY (item_id)
      REFERENCES items(item_id),
	FOREIGN KEY (tag_id)
	  REFERENCES tags(tag_id)
);

CREATE TABLE IF NOT EXISTS summoner_spells (
    ss_id INT UNIQUE NOT NULL,
    name VARCHAR(20),
    description VARCHAR(255),
    cooldown TINYINT,
    PRIMARY KEY (ss_id)
);