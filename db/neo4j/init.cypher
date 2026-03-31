// ============================================================
// Neo4j 5 – init.cypher – System Rezerwacji Wydarzeń
// Plik: db/neo4j/init.cypher
// ============================================================
// Ten plik NIE jest uruchamiany automatycznie przez Neo4j.
// Uruchonienie ręcznie przez:
//   docker exec -i neo4j_events cypher-shell -u neo4j -p test1234 < db/neo4j/init.cypher
// lub przez Neo4j Browser (http://localhost:7474)
// ============================================================


// ────────────────────────────────────────────────────────────
// CONSTRAINTS (unikalność + automatyczny indeks)
// ────────────────────────────────────────────────────────────

// User – unikalny email
CREATE CONSTRAINT constraint_user_email IF NOT EXISTS
FOR (u:User) REQUIRE u.email IS UNIQUE;

// User – unikalny user_id (najczesciej uzywany w MATCH)
CREATE CONSTRAINT constraint_user_id IF NOT EXISTS
FOR (u:User) REQUIRE u.user_id IS UNIQUE;

// Event – unikalny id
CREATE CONSTRAINT constraint_event_id IF NOT EXISTS
FOR (e:Event) REQUIRE e.event_id IS UNIQUE;

// Venue – unikalny id
CREATE CONSTRAINT constraint_venue_id IF NOT EXISTS
FOR (v:Venue) REQUIRE v.venue_id IS UNIQUE;

// Organizer – unikalny id
CREATE CONSTRAINT constraint_organizer_id IF NOT EXISTS
FOR (o:Organizer) REQUIRE o.organizer_id IS UNIQUE;

// Category – unikalna nazwa
CREATE CONSTRAINT constraint_category_name IF NOT EXISTS
FOR (c:Category) REQUIRE c.name IS UNIQUE;

// Booking – unikalny id
CREATE CONSTRAINT constraint_booking_id IF NOT EXISTS
FOR (b:Booking) REQUIRE b.booking_id IS UNIQUE;

// Ticket – unikalny id
CREATE CONSTRAINT constraint_ticket_id IF NOT EXISTS
FOR (t:Ticket) REQUIRE t.ticket_id IS UNIQUE;

// Zone – unikalny id
CREATE CONSTRAINT constraint_zone_id IF NOT EXISTS
FOR (z:Zone) REQUIRE z.zone_id IS UNIQUE;

// Payment – unikalny id
CREATE CONSTRAINT constraint_payment_id IF NOT EXISTS
FOR (p:Payment) REQUIRE p.payment_id IS UNIQUE;


// ────────────────────────────────────────────────────────────
// DODATKOWE INDEKSY (szybkie wyszukiwanie po właściwościach)
// ────────────────────────────────────────────────────────────

CREATE INDEX idx_user_status IF NOT EXISTS
FOR (u:User) ON (u.status);

CREATE INDEX idx_event_status IF NOT EXISTS
FOR (e:Event) ON (e.status);

CREATE INDEX idx_event_start_date IF NOT EXISTS
FOR (e:Event) ON (e.start_date);

CREATE INDEX idx_event_category IF NOT EXISTS
FOR (e:Event) ON (e.category);

CREATE INDEX idx_venue_city IF NOT EXISTS
FOR (v:Venue) ON (v.city);

CREATE INDEX idx_booking_status IF NOT EXISTS
FOR (b:Booking) ON (b.status);

CREATE INDEX idx_ticket_type IF NOT EXISTS
FOR (t:Ticket) ON (t.ticket_type);

CREATE INDEX idx_zone_type IF NOT EXISTS
FOR (z:Zone) ON (z.type);

CREATE INDEX idx_payment_status IF NOT EXISTS
FOR (p:Payment) ON (p.status);