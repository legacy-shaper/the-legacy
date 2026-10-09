-- 002 — Demonstration collection (fictional artists and works). Safe to re-run.
insert into public.collections (id,slug,name,subtitle,display_currency,cover_artwork_id) values
  ('a0e1d2c3-0000-4000-8000-00000000d3e0','demo-aurelian','The Aurelian Collection','Demonstration collection','USD','aur-08')
on conflict (id) do nothing;
insert into public.artworks (id,collection_id,ref,artist,title,year,medium,dimensions,edition_type,edition_number,owner_name,ownership_share,ownership_note,location_text,location_since,provenance,exhibitions,literature,condition,insured_value,insured_currency,acquisition_date,acquisition_price,acquisition_currency,acquisition_source,thumb) values
  ('aur-01','a0e1d2c3-0000-4000-8000-00000000d3e0','AUR-001','Élise Marchetti (b. 1971)','Crimson Threshold','2014','Oil on linen','130 x 100 cm','unique',null,'The Aurelian Family Trust',100,null,'Private residence · Geneva','2021-03-12','The artist
Private collection, Milan
Acquired from the above','Milan, private gallery, Élise Marchetti: Soglie, 2015','','Excellent. Condition report of 4 March 2026.',520000,'USD','2019-06-14',420000,'USD','Private sale','demo/aur-01-t.jpg'),
  ('aur-02','a0e1d2c3-0000-4000-8000-00000000d3e0','AUR-002','Élise Marchetti (b. 1971)','Nocturne in Ochre','2017','Oil on linen','130 x 100 cm','unique',null,'The Aurelian Family Trust',100,null,'Private residence · Dubai','2023-11-02','The artist
Acquired from the above',null,null,'Excellent',540000,'USD','2023-09-28',465000,'USD','Primary market','demo/aur-02-t.jpg'),
  ('aur-03','a0e1d2c3-0000-4000-8000-00000000d3e0','AUR-003','Henrik Aalto-Lind (1932–2009)','Composition with Arc','1968','Acrylic on canvas','110 x 110 cm','unique',null,'The Aurelian Family Trust',100,null,'Private residence · Geneva','2021-03-12','Estate of the artist
Private collection, Copenhagen
Acquired at auction','Copenhagen, retrospective exhibition, 1988','H. Aalto-Lind, Catalogue raisonné, vol. II, no. 214, ill.','Very good. Minor stabilised craquelure lower left.',950000,'EUR','2020-11-05',780000,'EUR','Evening sale, Paris','demo/aur-03-t.jpg'),
  ('aur-04','a0e1d2c3-0000-4000-8000-00000000d3e0','AUR-004','Yuna Takemori (b. 1984)','Blue Field I','2020','Pure pigment and resin on panel','100 x 100 cm','unique',null,'The Aurelian Family Trust',100,null,'Yacht · Capri','2024-05-20','The artist
Acquired from the above',null,null,'Excellent. Surface to be handled with gloves only.',210000,'USD','2021-04-17',145000,'USD','Primary market','demo/aur-04-t.jpg'),
  ('aur-05','a0e1d2c3-0000-4000-8000-00000000d3e0','AUR-005','Matteo Corvani (1928–1997)','Senza titolo (Movimento)','1959','Oil and enamel on canvas','100 x 130 cm','unique',null,'The Aurelian Family Trust',100,null,'Fine art storage · Geneva Freeport','2025-01-15','Private gallery, Milan
Private collection, Turin
Acquired at auction','Turin, museum exhibition, Corvani 1955–1965, 2003','M. Corvani, Opera completa, no. 59-07','Good. Conservation treatment completed February 2025.',1600000,'GBP','2018-10-19',1250000,'GBP','Evening sale, London','demo/aur-05-t.jpg'),
  ('aur-06','a0e1d2c3-0000-4000-8000-00000000d3e0','AUR-006','Matteo Corvani (1928–1997)','Senza titolo (Segno rosso)','1961','Oil on canvas','100 x 130 cm','unique',null,'The Aurelian Family Trust',50,'Held jointly with a family foundation (50 %)','On loan · museum exhibition, Lausanne','2026-09-01','Private collection, Rome
Acquired from the above','Lausanne, museum exhibition, September 2026 – January 2027 (on loan)',null,'Very good',1150000,'GBP','2022-06-24',980000,'GBP','Private sale','demo/aur-06-t.jpg'),
  ('aur-07','a0e1d2c3-0000-4000-8000-00000000d3e0','AUR-007','Lior Ben-Avram (b. 1979)','Notation (Grid 9)','2016','Gouache and graphite on paper','120 x 90 cm','unique',null,'The Aurelian Family Trust',100,null,'Private residence · Dubai','2023-11-02','The artist
Acquired from the above',null,null,'Excellent. Framed with UV-filtering glazing.',65000,'USD','2016-12-08',38000,'USD','Art fair, Basel','demo/aur-07-t.jpg'),
  ('aur-08','a0e1d2c3-0000-4000-8000-00000000d3e0','AUR-008','Céleste Moreau-Vidal (b. 1990)','Garden Rooms (Green)','2022','Acrylic on canvas','110 x 110 cm','unique',null,'The Aurelian Family Trust',100,null,'Private residence · Geneva','2022-12-01','The artist
Acquired from the above',null,null,'Excellent',90000,'EUR','2022-11-18',62000,'EUR','Primary market','demo/aur-08-t.jpg'),
  ('aur-09','a0e1d2c3-0000-4000-8000-00000000d3e0','AUR-009','Céleste Moreau-Vidal (b. 1990)','Garden Rooms (Dusk)','2023','Acrylic on canvas','110 x 110 cm','unique',null,'The Aurelian Family Trust',100,null,'Yacht · Capri','2024-05-20','The artist
Acquired from the above',null,null,'Excellent',95000,'EUR','2024-02-09',71000,'EUR','Primary market','demo/aur-09-t.jpg'),
  ('aur-10','a0e1d2c3-0000-4000-8000-00000000d3e0','AUR-010','Nadia Karami (b. 1986)','Horizon, Hatta','2021','Sumi ink on Japanese paper','90 x 140 cm','unique',null,'The Aurelian Family Trust',100,null,'Private residence · Dubai','2023-11-02','The artist
Acquired from the above',null,null,'Excellent',90000,'AED','2021-11-11',54000,'AED','Primary market','demo/aur-10-t.jpg'),
  ('aur-11','a0e1d2c3-0000-4000-8000-00000000d3e0','AUR-011','Arturo Velarde (1941–2018)','Figura en reposo','1994','Bronze with patina, on stone base','78 x 42 x 38 cm','edition','3/6','The Aurelian Family Trust',100,null,'Private residence · Geneva','2021-03-12','The artist
Private collection, Madrid
Acquired from the above',null,'A. Velarde, Esculturas 1960–2010, p. 188','Excellent. Wax renewed in 2025.',380000,'USD','2019-02-27',310000,'USD','Private sale','demo/aur-11-t.jpg'),
  ('aur-12','a0e1d2c3-0000-4000-8000-00000000d3e0','AUR-012','Yuna Takemori (b. 1984)','Red Field II','2022','Pure pigment and resin on panel','100 x 100 cm','unique',null,'The Aurelian Family Trust',100,null,'Fine art storage · Geneva Freeport','2025-01-15','The artist
Acquired from the above',null,null,'Excellent',225000,'USD','2025-01-10',168000,'USD','Primary market','demo/aur-12-t.jpg')
on conflict (id) do nothing;
insert into public.artwork_views (id,artwork_id,sort,photo) values
  ('00000000-0000-4000-8000-000000001001','aur-01',0,'demo/aur-01.jpg'),
  ('00000000-0000-4000-8000-000000001002','aur-01',1,'demo/aur-01-d.jpg'),
  ('00000000-0000-4000-8000-000000002001','aur-02',0,'demo/aur-02.jpg'),
  ('00000000-0000-4000-8000-000000003001','aur-03',0,'demo/aur-03.jpg'),
  ('00000000-0000-4000-8000-000000004001','aur-04',0,'demo/aur-04.jpg'),
  ('00000000-0000-4000-8000-000000005001','aur-05',0,'demo/aur-05.jpg'),
  ('00000000-0000-4000-8000-000000005002','aur-05',1,'demo/aur-05-d.jpg'),
  ('00000000-0000-4000-8000-000000006001','aur-06',0,'demo/aur-06.jpg'),
  ('00000000-0000-4000-8000-000000007001','aur-07',0,'demo/aur-07.jpg'),
  ('00000000-0000-4000-8000-000000008001','aur-08',0,'demo/aur-08.jpg'),
  ('00000000-0000-4000-8000-000000009001','aur-09',0,'demo/aur-09.jpg'),
  ('00000000-0000-4000-8000-000000010001','aur-10',0,'demo/aur-10.jpg'),
  ('00000000-0000-4000-8000-000000011001','aur-11',0,'demo/aur-11.jpg'),
  ('00000000-0000-4000-8000-000000011002','aur-11',1,'demo/aur-11-d.jpg'),
  ('00000000-0000-4000-8000-000000012001','aur-12',0,'demo/aur-12.jpg')
on conflict (id) do nothing;
insert into public.expenses (id,date,label,category,amount,currency,supplier,artwork_id,collection_id,visible_to_client,status) values
  ('demo-exp-001','2025-01-15','Annual fine art insurance premium','insurance',68500,'USD','Fine art insurer',null,'a0e1d2c3-0000-4000-8000-00000000d3e0',true,'paid'),
  ('demo-exp-002','2025-01-31','Geneva Freeport storage, annual','insurance',18400,'CHF','Freeport storage',null,'a0e1d2c3-0000-4000-8000-00000000d3e0',true,'paid'),
  ('demo-exp-003','2025-02-01','Collection Office, annual engagement','overhead',120000,'USD','Legacy Shaper Collection',null,'a0e1d2c3-0000-4000-8000-00000000d3e0',true,'paid'),
  ('demo-exp-004','2026-01-15','Annual fine art insurance premium','insurance',71200,'USD','Fine art insurer',null,'a0e1d2c3-0000-4000-8000-00000000d3e0',true,'paid'),
  ('demo-exp-005','2026-01-31','Geneva Freeport storage, annual','insurance',18900,'CHF','Freeport storage',null,'a0e1d2c3-0000-4000-8000-00000000d3e0',true,'paid'),
  ('demo-exp-006','2026-02-01','Collection Office, annual engagement','overhead',120000,'USD','Legacy Shaper Collection',null,'a0e1d2c3-0000-4000-8000-00000000d3e0',true,'paid'),
  ('demo-exp-007','2025-02-20','Conservation treatment','other',14500,'GBP','Conservation studio, London','aur-05','a0e1d2c3-0000-4000-8000-00000000d3e0',true,'paid'),
  ('demo-exp-008','2025-01-12','Transport and crating, Geneva → Freeport','transport',6200,'CHF','Fine art shipper','aur-05','a0e1d2c3-0000-4000-8000-00000000d3e0',true,'paid'),
  ('demo-exp-009','2024-05-14','Transport to yacht, Antibes','transport',9800,'EUR','Fine art shipper','aur-04','a0e1d2c3-0000-4000-8000-00000000d3e0',true,'paid'),
  ('demo-exp-010','2026-08-25','Loan transport and courier, Lausanne','transport',7400,'CHF','Fine art shipper','aur-06','a0e1d2c3-0000-4000-8000-00000000d3e0',true,'paid'),
  ('demo-exp-011','2026-03-04','Condition report','other',1800,'CHF','Independent conservator','aur-01','a0e1d2c3-0000-4000-8000-00000000d3e0',true,'paid'),
  ('demo-exp-012','2025-06-10','Bronze wax renewal','other',2600,'USD','Sculpture conservator','aur-11','a0e1d2c3-0000-4000-8000-00000000d3e0',true,'paid'),
  ('demo-exp-013','2026-01-10','Framing with UV-filtering glazing','other',4300,'AED','Framer, Dubai','aur-07','a0e1d2c3-0000-4000-8000-00000000d3e0',true,'paid'),
  ('demo-exp-014','2025-01-10','Transport and crating, studio → Freeport','transport',5100,'CHF','Fine art shipper','aur-12','a0e1d2c3-0000-4000-8000-00000000d3e0',true,'paid')
on conflict (id) do nothing;
