CREATE TABLE markov (
id INTEGER UNIQUE,
 word1 varchar(32), word2 varchar(32), word3 varchar(32), created integer);CREATE SEQUENCE markov_id_seq;
ALTER TABLE markov ALTER COLUMN id SET DEFAULT NEXTVAL('markov_id_seq');
CREATE INDEX idx_markov_12 ON markov (word1, word2);
CREATE INDEX idx_markov_12c ON markov (word1, word2, created);
CREATE INDEX idx_markov_2 ON markov (word2);
CREATE INDEX idx_markov_23 ON markov (word2, word3);
CREATE INDEX idx_markov_23c ON markov (word2, word3, created);
CREATE INDEX idx_markov_2c ON markov (word2, created);
