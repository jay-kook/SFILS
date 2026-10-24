-- Indexes added after loading the data (see results/README.md for the experiment)
CREATE INDEX idx_patrons_year_registered ON patrons(year_registered);
CREATE INDEX idx_patrons_total_checkouts ON patrons(total_checkouts);