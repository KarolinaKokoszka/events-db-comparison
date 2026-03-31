-- ============================================================
-- MySQL 8 init.sql – System Rezerwacji Wydarzeń (e-Ticket)
-- ============================================================
-- Różnice vs PostgreSQL:
--   • Brak CREATE TYPE – ENUM definiujemy inline
--   • BIGSERIAL → BIGINT AUTO_INCREMENT
--   • JSONB → JSON
--   • Brak GIN index – MySQL nie obsługuje; pomijamy indeksy na JSON
--   • UNIQUE inline zamiast osobnego CREATE INDEX (tam gdzie potrzeba)
--   • CHECK constraints wymagają MySQL 8.0.16+
-- ============================================================

SET FOREIGN_KEY_CHECKS = 0;

-- ────────────────────────────────────────────────────────────
-- TABELA: users
-- ────────────────────────────────────────────────────────────
CREATE TABLE users (
    id            BIGINT AUTO_INCREMENT PRIMARY KEY,
    first_name    VARCHAR(100) NOT NULL,
    last_name     VARCHAR(100) NOT NULL,
    email         VARCHAR(150) NOT NULL UNIQUE,
    password_hash TEXT         NOT NULL,
    phone         VARCHAR(20),
    status        ENUM('active', 'deleted') DEFAULT 'active',
    created_at    DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at    DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);

CREATE INDEX idx_users_status ON users(status);

-- ────────────────────────────────────────────────────────────
-- TABELA: user_addresses
-- ────────────────────────────────────────────────────────────
CREATE TABLE user_addresses (
    id          BIGINT AUTO_INCREMENT PRIMARY KEY,
    user_id     BIGINT       NOT NULL,
    street      VARCHAR(150) NOT NULL,
    city        VARCHAR(100) NOT NULL,
    postal_code VARCHAR(20)  NOT NULL,
    country     VARCHAR(100) NOT NULL,
    type        ENUM('home', 'billing', 'other') NOT NULL,
    created_at  DATETIME DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT fk_addr_user FOREIGN KEY (user_id)
        REFERENCES users(id) ON DELETE CASCADE
);

CREATE INDEX idx_addresses_user ON user_addresses(user_id);

-- ────────────────────────────────────────────────────────────
-- TABELA: organizers
-- ────────────────────────────────────────────────────────────
CREATE TABLE organizers (
    id         BIGINT AUTO_INCREMENT PRIMARY KEY,
    name       VARCHAR(150) NOT NULL,
    email      VARCHAR(150),
    phone      VARCHAR(20),
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- ────────────────────────────────────────────────────────────
-- TABELA: venues
-- ────────────────────────────────────────────────────────────
CREATE TABLE venues (
    id          BIGINT AUTO_INCREMENT PRIMARY KEY,
    name        VARCHAR(150) NOT NULL,
    street      VARCHAR(150) NOT NULL,
    city        VARCHAR(100) NOT NULL,
    postal_code VARCHAR(20),
    country     VARCHAR(100) NOT NULL,
    capacity    INT          NOT NULL,
    created_at  DATETIME DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT chk_venue_capacity CHECK (capacity > 0)
);

CREATE INDEX idx_venues_city ON venues(city);

-- ────────────────────────────────────────────────────────────
-- TABELA: categories
-- ────────────────────────────────────────────────────────────
CREATE TABLE categories (
    id   BIGINT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(100) NOT NULL UNIQUE
);

-- ────────────────────────────────────────────────────────────
-- TABELA: events
-- ────────────────────────────────────────────────────────────
CREATE TABLE events (
    id              BIGINT AUTO_INCREMENT PRIMARY KEY,
    name            VARCHAR(200) NOT NULL,
    description     TEXT,
    category_id     BIGINT,
    organizer_id    BIGINT,
    venue_id        BIGINT,
    start_date      DATETIME     NOT NULL,
    end_date        DATETIME     NOT NULL,
    additional_info JSON,
    -- Przykład: {"age_limit": 18, "dress_code": "casual", "parking": true, "languages": ["PL","EN"]}
    status          ENUM('planned', 'active', 'cancelled', 'finished') DEFAULT 'planned',
    created_at      DATETIME DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT fk_events_category  FOREIGN KEY (category_id)  REFERENCES categories(id),
    CONSTRAINT fk_events_organizer FOREIGN KEY (organizer_id) REFERENCES organizers(id),
    CONSTRAINT fk_events_venue     FOREIGN KEY (venue_id)     REFERENCES venues(id)
);

CREATE INDEX idx_events_status     ON events(status);
CREATE INDEX idx_events_start_date ON events(start_date);
CREATE INDEX idx_events_category   ON events(category_id);
CREATE INDEX idx_events_venue      ON events(venue_id);
CREATE INDEX idx_events_organizer  ON events(organizer_id);

-- ────────────────────────────────────────────────────────────
-- TABELA: event_zones
-- ────────────────────────────────────────────────────────────
CREATE TABLE event_zones (
    id       BIGINT AUTO_INCREMENT PRIMARY KEY,
    event_id BIGINT       NOT NULL,
    name     VARCHAR(100) NOT NULL,
    type     ENUM('numbered', 'general') NOT NULL,
    capacity INT          NOT NULL,

    CONSTRAINT chk_zone_capacity CHECK (capacity > 0),
    CONSTRAINT uq_zone_event_name UNIQUE (event_id, name),
    CONSTRAINT fk_zones_event FOREIGN KEY (event_id)
        REFERENCES events(id) ON DELETE CASCADE
);

CREATE INDEX idx_zones_event ON event_zones(event_id);

-- ────────────────────────────────────────────────────────────
-- TABELA: seats  (tylko dla stref numerowanych)
-- ────────────────────────────────────────────────────────────
CREATE TABLE seats (
    id          BIGINT AUTO_INCREMENT PRIMARY KEY,
    zone_id     BIGINT      NOT NULL,
    row_label   VARCHAR(10) NOT NULL,
    seat_number INT         NOT NULL,

    CONSTRAINT uq_seat UNIQUE (zone_id, row_label, seat_number),
    CONSTRAINT fk_seats_zone FOREIGN KEY (zone_id)
        REFERENCES event_zones(id) ON DELETE CASCADE
);

CREATE INDEX idx_seats_zone ON seats(zone_id);

-- ────────────────────────────────────────────────────────────
-- TABELA: tickets
-- ────────────────────────────────────────────────────────────
CREATE TABLE tickets (
    id                 BIGINT AUTO_INCREMENT PRIMARY KEY,
    event_id           BIGINT        NOT NULL,
    zone_id            BIGINT        NOT NULL,
    seat_id            BIGINT,                     -- NULL dla strefy 'general'
    ticket_type        VARCHAR(50),
    total_quantity     INT           NOT NULL,
    available_quantity INT           NOT NULL,
    price              DECIMAL(10,2) NOT NULL,
    perks              JSON,
    -- Przykład: {"lounge_access": true, "backstage_pass": false, "free_drink": true}
    status             VARCHAR(30)   DEFAULT 'available',
    created_at         DATETIME DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT chk_ticket_avail    CHECK (available_quantity >= 0),
    CONSTRAINT chk_ticket_qty      CHECK (available_quantity <= total_quantity),
    CONSTRAINT fk_tickets_event    FOREIGN KEY (event_id) REFERENCES events(id),
    CONSTRAINT fk_tickets_zone     FOREIGN KEY (zone_id)  REFERENCES event_zones(id),
    CONSTRAINT fk_tickets_seat     FOREIGN KEY (seat_id)  REFERENCES seats(id)
);

CREATE INDEX idx_tickets_event  ON tickets(event_id);
CREATE INDEX idx_tickets_zone   ON tickets(zone_id);
CREATE INDEX idx_tickets_status ON tickets(status);

-- ────────────────────────────────────────────────────────────
-- TABELA: bookings
-- ────────────────────────────────────────────────────────────
CREATE TABLE bookings (
    id           BIGINT AUTO_INCREMENT PRIMARY KEY,
    user_id      BIGINT        NOT NULL,
    booking_date DATETIME      DEFAULT CURRENT_TIMESTAMP,
    status       ENUM('pending', 'paid', 'cancelled') DEFAULT 'pending',
    total_price  DECIMAL(10,2) NOT NULL,

    CONSTRAINT chk_booking_price CHECK (total_price >= 0),
    CONSTRAINT fk_bookings_user  FOREIGN KEY (user_id)
        REFERENCES users(id) ON DELETE CASCADE
);

CREATE INDEX idx_bookings_user   ON bookings(user_id);
CREATE INDEX idx_bookings_status ON bookings(status);
CREATE INDEX idx_bookings_date   ON bookings(booking_date);

-- ────────────────────────────────────────────────────────────
-- TABELA: booking_tickets
-- ────────────────────────────────────────────────────────────
CREATE TABLE booking_tickets (
    id                BIGINT AUTO_INCREMENT PRIMARY KEY,
    booking_id        BIGINT        NOT NULL,
    ticket_id         BIGINT        NOT NULL,
    quantity          INT           NOT NULL,
    price_at_purchase DECIMAL(10,2) NOT NULL,

    CONSTRAINT chk_bt_quantity    CHECK (quantity > 0),
    CONSTRAINT fk_bt_booking      FOREIGN KEY (booking_id)
        REFERENCES bookings(id) ON DELETE CASCADE,
    CONSTRAINT fk_bt_ticket       FOREIGN KEY (ticket_id)
        REFERENCES tickets(id)
);

CREATE INDEX idx_booking_tickets_booking ON booking_tickets(booking_id);
CREATE INDEX idx_booking_tickets_ticket  ON booking_tickets(ticket_id);

-- ────────────────────────────────────────────────────────────
-- TABELA: payments
-- ────────────────────────────────────────────────────────────
CREATE TABLE payments (
    id             BIGINT AUTO_INCREMENT PRIMARY KEY,
    booking_id     BIGINT        NOT NULL,
    payment_method VARCHAR(50),
    amount         DECIMAL(10,2),
    payment_date   DATETIME,
    status         VARCHAR(30),

    CONSTRAINT fk_payments_booking FOREIGN KEY (booking_id)
        REFERENCES bookings(id)
);

CREATE INDEX idx_payments_booking ON payments(booking_id);
CREATE INDEX idx_payments_status  ON payments(status);

-- ────────────────────────────────────────────────────────────
-- TABELA: reviews
-- ────────────────────────────────────────────────────────────
CREATE TABLE reviews (
    id         BIGINT AUTO_INCREMENT PRIMARY KEY,
    user_id    BIGINT,
    event_id   BIGINT,
    rating     INT  NOT NULL,
    comment    TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT chk_rating         CHECK (rating BETWEEN 1 AND 5),
    CONSTRAINT uq_review          UNIQUE (user_id, event_id),
    CONSTRAINT fk_reviews_user    FOREIGN KEY (user_id)
        REFERENCES users(id)  ON DELETE SET NULL,
    CONSTRAINT fk_reviews_event   FOREIGN KEY (event_id)
        REFERENCES events(id) ON DELETE CASCADE
);

CREATE INDEX idx_reviews_event ON reviews(event_id);
CREATE INDEX idx_reviews_user  ON reviews(user_id);

SET FOREIGN_KEY_CHECKS = 1;