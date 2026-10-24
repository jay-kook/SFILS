USE sfils;

DROP TABLE IF EXISTS patrons;
DROP TABLE IF EXISTS library_codes;
DROP TABLE IF EXISTS branches;
DROP TABLE IF EXISTS notification_preferences;
DROP TABLE IF EXISTS age_ranges;
DROP TABLE IF EXISTS patron_types;

CREATE TABLE patron_types (
    patron_type_code INT PRIMARY KEY,
    patron_type_name VARCHAR(50) NOT NULL
);

CREATE TABLE age_ranges (
    age_range_id INT AUTO_INCREMENT PRIMARY KEY,
    age_range_label VARCHAR(30) NOT NULL UNIQUE,
    sort_order TINYINT NOT NULL
);

CREATE TABLE notification_preferences (
    notification_code CHAR(1) PRIMARY KEY,
    notification_name VARCHAR(20) NOT NULL
);

CREATE TABLE branches (
    branch_id INT AUTO_INCREMENT PRIMARY KEY,
    branch_name VARCHAR(50) NOT NULL UNIQUE
);

CREATE TABLE library_codes (
    library_code VARCHAR(10) PRIMARY KEY,
    branch_id INT NOT NULL,
    FOREIGN KEY (branch_id) REFERENCES branches(branch_id)
);

CREATE TABLE patrons (
    patron_id INT AUTO_INCREMENT PRIMARY KEY,
    patron_type_code INT NOT NULL,
    age_range_id INT NULL,
    home_library_code VARCHAR(10) NULL,
    notification_code CHAR(1) NOT NULL,
    total_checkouts INT NOT NULL,
    total_renewals INT NOT NULL,
    active_month VARCHAR(10) NULL,
    active_year SMALLINT NULL,
    provided_email BOOLEAN NOT NULL,
    within_sf_county BOOLEAN NOT NULL,
    year_registered SMALLINT NOT NULL,
    FOREIGN KEY (patron_type_code) REFERENCES patron_types(patron_type_code),
    FOREIGN KEY (age_range_id) REFERENCES age_ranges(age_range_id),
    FOREIGN KEY (home_library_code) REFERENCES library_codes(library_code),
    FOREIGN KEY (notification_code) REFERENCES notification_preferences(notification_code)
);