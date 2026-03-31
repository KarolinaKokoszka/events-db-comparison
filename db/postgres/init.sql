-- ============================================================
-- PostgreSQL init.sql – System Rezerwacji Wydarzeń (e-Ticket)
-- ============================================================

-- ────────────────────────────────────────────────────────────
-- TYPY ENUM
-- ────────────────────────────────────────────────────────────
CREATE TYPE user_status    AS ENUM ('active', 'deleted');
CREATE TYPE address_type   AS ENUM ('home', 'billing', 'other');
CREATE TYPE event_status   AS ENUM ('planned', 'active', 'cancelled', 'finished');
CREATE TYPE zone_type      AS ENUM ('numbered', 'general');
CREATE TYPE booking_status AS ENUM ('pending', 'paid', 'cancelled');

-- ────────────────────────────────────────────────────────────
-- TABELA: users
-- ────────────────────────────────────────────────────────────
CREATE TABLE users (
    id            BIGSERIAL PRIMARY KEY,
    first_name    VARCHAR(100) NOT NULL,
    last_name     VARCHAR(100) NOT NULL,
    email         VARCHAR(150) NOT NULL UNIQUE,
    password_hash TEXT         NOT NULL,
    phone         VARCHAR(20),
    status        user_status  DEFAULT 'active',
    created_at    TIMESTAMP    DEFAULT CURRENT_TIMESTAMP,
    updated_at    TIMESTAMP    DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_users_email  ON users(email);
CREATE INDEX idx_users_status ON users(status);

-- ────────────────────────────────────────────────────────────
-- TABELA: user_addresses
-- ────────────────────────────────────────────────────────────
CREATE TABLE user_addresses (
    id          BIGSERIAL    PRIMARY KEY,
    user_id     BIGINT       NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    street      VARCHAR(150) NOT NULL,
    city        VARCHAR(100) NOT NULL,
    postal_code VARCHAR(20)  NOT NULL,
    country     VARCHAR(100) NOT NULL,
    type        address_type NOT NULL,
    created_at  TIMESTAMP    DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_addresses_user ON user_addresses(user_id);

-- ────────────────────────────────────────────────────────────
-- TABELA: organizers
-- ────────────────────────────────────────────────────────────
CREATE TABLE organizers (
    id         BIGSERIAL    PRIMARY KEY,
    name       VARCHAR(150) NOT NULL,
    email      VARCHAR(150),
    phone      VARCHAR(20),
    created_at TIMESTAMP    DEFAULT CURRENT_TIMESTAMP
);

-- ────────────────────────────────────────────────────────────
-- TABELA: venues
-- ────────────────────────────────────────────────────────────
CREATE TABLE venues (
    id          BIGSERIAL    PRIMARY KEY,
    name        VARCHAR(150) NOT NULL,
    street      VARCHAR(150) NOT NULL,
    city        VARCHAR(100) NOT NULL,
    postal_code VARCHAR(20),
    country     VARCHAR(100) NOT NULL,
    capacity    INT          NOT NULL CHECK (capacity > 0),
    created_at  TIMESTAMP    DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_venues_city ON venues(city);

-- ────────────────────────────────────────────────────────────
-- TABELA: categories
-- ────────────────────────────────────────────────────────────
CREATE TABLE categories (
    id   BIGSERIAL    PRIMARY KEY,
    name VARCHAR(100) NOT NULL UNIQUE
);

-- ────────────────────────────────────────────────────────────
-- TABELA: events
-- ────────────────────────────────────────────────────────────
CREATE TABLE events (
    id              BIGSERIAL    PRIMARY KEY,
    name            VARCHAR(200) NOT NULL,
    description     TEXT,
    category_id     BIGINT       REFERENCES categories(id),
    organizer_id    BIGINT       REFERENCES organizers(id),
    venue_id        BIGINT       REFERENCES venues(id),
    start_date      TIMESTAMP    NOT NULL,
    end_date        TIMESTAMP    NOT NULL,
    additional_info JSONB,
    -- Przykład: {"age_limit": 18, "dress_code": "casual", "parking": true, "languages": ["PL","EN"]}
    status          event_status DEFAULT 'planned',
    created_at      TIMESTAMP    DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_events_status       ON events(status);
CREATE INDEX idx_events_start_date   ON events(start_date);
CREATE INDEX idx_events_category     ON events(category_id);
CREATE INDEX idx_events_venue        ON events(venue_id);
CREATE INDEX idx_events_organizer    ON events(organizer_id);
CREATE INDEX idx_events_add_info     ON events USING GIN (additional_info);

-- ────────────────────────────────────────────────────────────
-- TABELA: event_zones
-- ────────────────────────────────────────────────────────────
CREATE TABLE event_zones (
    id       BIGSERIAL    PRIMARY KEY,
    event_id BIGINT       NOT NULL REFERENCES events(id) ON DELETE CASCADE,
    name     VARCHAR(100) NOT NULL,   -- np. Trybuna A, Płyta, VIP
    type     zone_type    NOT NULL,
    capacity INT          NOT NULL CHECK (capacity > 0),
    UNIQUE (event_id, name)
);

CREATE INDEX idx_zones_event ON event_zones(event_id);

-- ────────────────────────────────────────────────────────────
-- TABELA: seats  (tylko dla stref numerowanych)
-- ────────────────────────────────────────────────────────────
CREATE TABLE seats (
    id          BIGSERIAL   PRIMARY KEY,
    zone_id     BIGINT      NOT NULL REFERENCES event_zones(id) ON DELETE CASCADE,
    row_label   VARCHAR(10) NOT NULL,
    seat_number INT         NOT NULL,
    UNIQUE (zone_id, row_label, seat_number)
);

CREATE INDEX idx_seats_zone ON seats(zone_id);

-- ────────────────────────────────────────────────────────────
-- TABELA: tickets
-- ────────────────────────────────────────────────────────────
CREATE TABLE tickets (
    id                 BIGSERIAL      PRIMARY KEY,
    event_id           BIGINT         NOT NULL REFERENCES events(id),
    zone_id            BIGINT         NOT NULL REFERENCES event_zones(id),
    seat_id            BIGINT         REFERENCES seats(id),   -- NULL dla strefy 'general'
    ticket_type        VARCHAR(50),
    total_quantity     INT            NOT NULL,
    available_quantity INT            NOT NULL,
    price              DECIMAL(10,2)  NOT NULL,
    perks              JSONB,
    -- Przykład: {"lounge_access": true, "backstage_pass": false, "free_drink": true}
    status             VARCHAR(30)    DEFAULT 'available',
    created_at         TIMESTAMP      DEFAULT CURRENT_TIMESTAMP,

    CHECK (available_quantity >= 0),
    CHECK (available_quantity <= total_quantity),
    CHECK (
        (seat_id IS NOT NULL AND total_quantity = 1)
        OR
        (seat_id IS NULL)
    )
);

CREATE INDEX idx_tickets_event     ON tickets(event_id);
CREATE INDEX idx_tickets_zone      ON tickets(zone_id);
CREATE INDEX idx_tickets_status    ON tickets(status);
CREATE INDEX idx_tickets_perks     ON tickets USING GIN (perks);

-- ────────────────────────────────────────────────────────────
-- TABELA: bookings
-- ────────────────────────────────────────────────────────────
CREATE TABLE bookings (
    id           BIGSERIAL      PRIMARY KEY,
    user_id      BIGINT         NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    booking_date TIMESTAMP      DEFAULT CURRENT_TIMESTAMP,
    status       booking_status DEFAULT 'pending',
    total_price  DECIMAL(10,2)  NOT NULL CHECK (total_price >= 0)
);

CREATE INDEX idx_bookings_user   ON bookings(user_id);
CREATE INDEX idx_bookings_status ON bookings(status);
CREATE INDEX idx_bookings_date   ON bookings(booking_date);

-- ────────────────────────────────────────────────────────────
-- TABELA: booking_tickets
-- ────────────────────────────────────────────────────────────
CREATE TABLE booking_tickets (
    id                BIGSERIAL     PRIMARY KEY,
    booking_id        BIGINT        NOT NULL REFERENCES bookings(id) ON DELETE CASCADE,
    ticket_id         BIGINT        NOT NULL REFERENCES tickets(id),
    quantity          INT           NOT NULL CHECK (quantity > 0),
    price_at_purchase DECIMAL(10,2) NOT NULL
);

CREATE INDEX idx_booking_tickets_booking ON booking_tickets(booking_id);
CREATE INDEX idx_booking_tickets_ticket  ON booking_tickets(ticket_id);

-- ────────────────────────────────────────────────────────────
-- TABELA: payments
-- ────────────────────────────────────────────────────────────
CREATE TABLE payments (
    id             BIGSERIAL     PRIMARY KEY,
    booking_id     BIGINT        NOT NULL REFERENCES bookings(id),
    payment_method VARCHAR(50),
    amount         DECIMAL(10,2),
    payment_date   TIMESTAMP,
    status         VARCHAR(30)
);

CREATE INDEX idx_payments_booking ON payments(booking_id);
CREATE INDEX idx_payments_status  ON payments(status);

-- ────────────────────────────────────────────────────────────
-- TABELA: reviews
-- ────────────────────────────────────────────────────────────
CREATE TABLE reviews (
    id         BIGSERIAL PRIMARY KEY,
    user_id    BIGINT    REFERENCES users(id)  ON DELETE SET NULL,
    event_id   BIGINT    REFERENCES events(id) ON DELETE CASCADE,
    rating     INT       NOT NULL CHECK (rating BETWEEN 1 AND 5),
    comment    TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (user_id, event_id)
);

CREATE INDEX idx_reviews_event ON reviews(event_id);
CREATE INDEX idx_reviews_user  ON reviews(user_id);