-- Datenbankstruktur der Pokémon-Sammlung (PostgreSQL). Enthält keine Sammlungsdaten.
-- Auf einer leeren Datenbank einmal komplett ausführen.

CREATE TABLE public.karten (
    karten_id integer NOT NULL,
    api_id text,
    name text NOT NULL,
    pokemon text,
    nummer text NOT NULL,
    set_id text NOT NULL,
    raritaet_id integer,
    bild_pfad text,
    cm_id integer,
    cm_unsicher boolean DEFAULT false NOT NULL,
    bild_de text,
    preis_manuell numeric(10,2),
    preis_manuell_quelle text
);


CREATE SEQUENCE public.karten_karten_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

CREATE TABLE public.katalog_karten (
    tcg_set text NOT NULL,
    nr text NOT NULL,
    name_de text,
    name_en text,
    seltenheit text,
    kategorie text,
    varianten text,
    cm_id integer,
    cm_unsicher boolean DEFAULT false NOT NULL
);


CREATE TABLE public.katalog_sets (
    tcg_id text NOT NULL,
    name_de text,
    name_en text,
    serie_id text,
    serie_de text,
    serie_en text,
    erscheinung date,
    anzahl integer,
    kuerzel text,
    set_id text
);


CREATE TABLE public.preis_karten (
    karten_id integer NOT NULL,
    datum date DEFAULT CURRENT_DATE NOT NULL,
    preis_cm numeric(10,2),
    preis_ab numeric(10,2),
    preis_reverse numeric(10,2)
);


CREATE TABLE public.preis_produkte (
    produkt_id integer NOT NULL,
    datum date DEFAULT CURRENT_DATE NOT NULL,
    preis_cm numeric(10,2),
    preis_ab numeric(10,2)
);


CREATE TABLE public.produkt_typen (
    typ_id integer NOT NULL,
    name text NOT NULL,
    uvp numeric(10,2)
);


CREATE SEQUENCE public.produkt_typen_typ_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

CREATE TABLE public.produkte (
    produkt_id integer NOT NULL,
    name text NOT NULL,
    sprache text NOT NULL,
    typ_id integer NOT NULL,
    set_id text,
    bild_pfad text,
    cm_id integer,
    cm_unsicher boolean DEFAULT false NOT NULL,
    preis_manuell numeric(10,2),
    preis_manuell_quelle text,
    CONSTRAINT produkte_sprache_check CHECK ((sprache = ANY (ARRAY['DE'::text, 'EN'::text, 'JP'::text, 'KR'::text, 'ZH'::text])))
);


CREATE SEQUENCE public.produkte_produkt_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

CREATE TABLE public.raritaeten (
    raritaet_id integer NOT NULL,
    name text NOT NULL
);


CREATE SEQUENCE public.raritaeten_raritaet_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

CREATE TABLE public.sammlung_karten (
    id integer NOT NULL,
    karten_id integer NOT NULL,
    anzahl integer DEFAULT 1 NOT NULL,
    sprache text DEFAULT 'DE'::text NOT NULL,
    zustand text DEFAULT 'NM'::text NOT NULL,
    foto_pfad text,
    variante text DEFAULT 'Normal'::text NOT NULL,
    notiz text,
    CONSTRAINT sammlung_karten_anzahl_check CHECK ((anzahl > 0)),
    CONSTRAINT sammlung_karten_sprache_check CHECK ((sprache = ANY (ARRAY['DE'::text, 'EN'::text, 'JP'::text, 'KR'::text, 'ZH'::text]))),
    CONSTRAINT sammlung_karten_variante_check CHECK ((variante = ANY (ARRAY['Normal'::text, 'Holo'::text, 'Reverse Holo'::text, 'Pokéball Reverse Holo'::text, 'Masterball Reverse Holo'::text, 'First Edition'::text]))),
    CONSTRAINT sammlung_karten_zustand_check CHECK ((zustand = ANY (ARRAY['M'::text, 'NM'::text, 'EX'::text, 'GD'::text, 'LP'::text, 'PL'::text, 'PO'::text])))
);


CREATE SEQUENCE public.sammlung_karten_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

CREATE TABLE public.sammlung_produkte (
    produkt_id integer NOT NULL,
    anzahl integer DEFAULT 1 NOT NULL,
    kaufpreis numeric(10,2),
    notiz text,
    CONSTRAINT sammlung_produkte_anzahl_check CHECK ((anzahl > 0))
);


CREATE TABLE public.sets (
    set_id text NOT NULL,
    name text NOT NULL,
    serie text,
    erscheinungsdatum date
);


ALTER TABLE ONLY public.karten ALTER COLUMN karten_id SET DEFAULT nextval('public.karten_karten_id_seq'::regclass);

ALTER TABLE ONLY public.produkt_typen ALTER COLUMN typ_id SET DEFAULT nextval('public.produkt_typen_typ_id_seq'::regclass);

ALTER TABLE ONLY public.produkte ALTER COLUMN produkt_id SET DEFAULT nextval('public.produkte_produkt_id_seq'::regclass);

ALTER TABLE ONLY public.raritaeten ALTER COLUMN raritaet_id SET DEFAULT nextval('public.raritaeten_raritaet_id_seq'::regclass);

ALTER TABLE ONLY public.sammlung_karten ALTER COLUMN id SET DEFAULT nextval('public.sammlung_karten_id_seq'::regclass);

ALTER TABLE ONLY public.karten
    ADD CONSTRAINT karten_api_id_key UNIQUE (api_id);

ALTER TABLE ONLY public.karten
    ADD CONSTRAINT karten_pkey PRIMARY KEY (karten_id);

ALTER TABLE ONLY public.katalog_karten
    ADD CONSTRAINT katalog_karten_pkey PRIMARY KEY (tcg_set, nr);

ALTER TABLE ONLY public.katalog_sets
    ADD CONSTRAINT katalog_sets_pkey PRIMARY KEY (tcg_id);

ALTER TABLE ONLY public.preis_karten
    ADD CONSTRAINT preis_karten_pkey PRIMARY KEY (karten_id, datum);

ALTER TABLE ONLY public.preis_produkte
    ADD CONSTRAINT preis_produkte_pkey PRIMARY KEY (produkt_id, datum);

ALTER TABLE ONLY public.produkt_typen
    ADD CONSTRAINT produkt_typen_name_key UNIQUE (name);

ALTER TABLE ONLY public.produkt_typen
    ADD CONSTRAINT produkt_typen_pkey PRIMARY KEY (typ_id);

ALTER TABLE ONLY public.produkte
    ADD CONSTRAINT produkte_name_sprache_key UNIQUE (name, sprache);

ALTER TABLE ONLY public.produkte
    ADD CONSTRAINT produkte_pkey PRIMARY KEY (produkt_id);

ALTER TABLE ONLY public.raritaeten
    ADD CONSTRAINT raritaeten_name_key UNIQUE (name);

ALTER TABLE ONLY public.raritaeten
    ADD CONSTRAINT raritaeten_pkey PRIMARY KEY (raritaet_id);

ALTER TABLE ONLY public.sammlung_karten
    ADD CONSTRAINT sammlung_karten_eindeutig UNIQUE (karten_id, sprache, zustand, variante);

ALTER TABLE ONLY public.sammlung_karten
    ADD CONSTRAINT sammlung_karten_pkey PRIMARY KEY (id);

ALTER TABLE ONLY public.sammlung_produkte
    ADD CONSTRAINT sammlung_produkte_pkey PRIMARY KEY (produkt_id);

ALTER TABLE ONLY public.sets
    ADD CONSTRAINT sets_pkey PRIMARY KEY (set_id);

CREATE INDEX idx_karten_raritaet ON public.karten USING btree (raritaet_id);

CREATE INDEX idx_karten_set ON public.karten USING btree (set_id);

CREATE INDEX idx_produkte_set ON public.produkte USING btree (set_id);

CREATE INDEX idx_produkte_typ ON public.produkte USING btree (typ_id);

CREATE INDEX katalog_karten_de ON public.katalog_karten USING btree (lower(name_de));

CREATE INDEX katalog_karten_en ON public.katalog_karten USING btree (lower(name_en));

ALTER TABLE ONLY public.karten
    ADD CONSTRAINT karten_raritaet_id_fkey FOREIGN KEY (raritaet_id) REFERENCES public.raritaeten(raritaet_id);

ALTER TABLE ONLY public.karten
    ADD CONSTRAINT karten_set_id_fkey FOREIGN KEY (set_id) REFERENCES public.sets(set_id);

ALTER TABLE ONLY public.katalog_karten
    ADD CONSTRAINT katalog_karten_tcg_set_fkey FOREIGN KEY (tcg_set) REFERENCES public.katalog_sets(tcg_id);

ALTER TABLE ONLY public.preis_karten
    ADD CONSTRAINT preis_karten_karten_id_fkey FOREIGN KEY (karten_id) REFERENCES public.karten(karten_id);

ALTER TABLE ONLY public.preis_produkte
    ADD CONSTRAINT preis_produkte_produkt_id_fkey FOREIGN KEY (produkt_id) REFERENCES public.produkte(produkt_id);

ALTER TABLE ONLY public.produkte
    ADD CONSTRAINT produkte_set_id_fkey FOREIGN KEY (set_id) REFERENCES public.sets(set_id);

ALTER TABLE ONLY public.produkte
    ADD CONSTRAINT produkte_typ_id_fkey FOREIGN KEY (typ_id) REFERENCES public.produkt_typen(typ_id);

ALTER TABLE ONLY public.sammlung_karten
    ADD CONSTRAINT sammlung_karten_karten_id_fkey FOREIGN KEY (karten_id) REFERENCES public.karten(karten_id);

ALTER TABLE ONLY public.sammlung_produkte
    ADD CONSTRAINT sammlung_produkte_produkt_id_fkey FOREIGN KEY (produkt_id) REFERENCES public.produkte(produkt_id);

ALTER TABLE public.karten ENABLE ROW LEVEL SECURITY;

ALTER TABLE public.katalog_karten ENABLE ROW LEVEL SECURITY;

ALTER TABLE public.katalog_sets ENABLE ROW LEVEL SECURITY;

ALTER TABLE public.preis_karten ENABLE ROW LEVEL SECURITY;

ALTER TABLE public.preis_produkte ENABLE ROW LEVEL SECURITY;

ALTER TABLE public.produkt_typen ENABLE ROW LEVEL SECURITY;

ALTER TABLE public.produkte ENABLE ROW LEVEL SECURITY;

ALTER TABLE public.raritaeten ENABLE ROW LEVEL SECURITY;

ALTER TABLE public.sammlung_karten ENABLE ROW LEVEL SECURITY;

ALTER TABLE public.sammlung_produkte ENABLE ROW LEVEL SECURITY;

ALTER TABLE public.sets ENABLE ROW LEVEL SECURITY;

-- Auswahllisten
INSERT INTO produkt_typen (name) VALUES
    ('Booster'), ('Boosterbundle'), ('Display'), ('Top Trainer Box'), ('Kollektion'), ('Tin'), ('Blister'),
    ('Kampfdeck'), ('Sonstiges'), ('Premium Kollektion'), ('Ultra Premium Kollektion'),
    ('Super Premium Kollektion'), ('Mini Tin');

INSERT INTO raritaeten (name) VALUES
    ('Common'), ('Uncommon'), ('Rare'), ('Rare Holo'), ('Double Rare'), ('Ultra Rare'), ('Illustration Rare'),
    ('Special Illustration Rare'), ('Hyper Rare'), ('Promo');
