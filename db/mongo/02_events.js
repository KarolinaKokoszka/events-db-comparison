// ============================================================
// MongoDB – Kolekcja: events
// Plik: db/mongo/02_events.js
// ============================================================

db = db.getSiblingDB('eventsdb');

db.createCollection('events', {
  validator: {
    $jsonSchema: {
      bsonType: 'object',
      required: ['name', 'status', 'start_date', 'end_date', 'organizer', 'venue'],
      properties: {
        name: {
          bsonType: 'string',
          description: 'Nazwa wydarzenia – wymagana'
        },
        description: {
          bsonType: ['string', 'null']
        },
        status: {
          bsonType: 'string',
          enum: ['planned', 'active', 'cancelled', 'finished']
        },
        start_date: { bsonType: 'date' },
        end_date:   { bsonType: 'date' },

        // Denormalizacja: kategoria jako string (nazwa)
        category: {
          bsonType: ['string', 'null'],
          description: 'Nazwa kategorii – denormalizowana'
        },

        // additional_info – dane półustrukturalne (kluczowe dla projektu!)
        additional_info: {
          bsonType: ['object', 'null'],
          description: 'Dodatkowe informacje o wydarzeniu (JSON)',
          properties: {
            age_limit:  { bsonType: ['int', 'null'] },
            dress_code: { bsonType: ['string', 'null'] },
            parking:    { bsonType: ['bool', 'null'] },
            languages:  { bsonType: ['array', 'null'] }
          }
        },

        // Organizator wbudowany – denormalizacja
        organizer: {
          bsonType: 'object',
          required: ['name'],
          properties: {
            name:  { bsonType: 'string' },
            email: { bsonType: ['string', 'null'] },
            phone: { bsonType: ['string', 'null'] }
          }
        },

        // Venue wbudowane – denormalizacja
        venue: {
          bsonType: 'object',
          required: ['name', 'city', 'country'],
          properties: {
            name:        { bsonType: 'string' },
            street:      { bsonType: ['string', 'null'] },
            city:        { bsonType: 'string' },
            postal_code: { bsonType: ['string', 'null'] },
            country:     { bsonType: 'string' },
            capacity:    { bsonType: ['int', 'null'] }
          }
        },

        // Strefy i bilety wbudowane
        zones: {
          bsonType: ['array', 'null'],
          items: {
            bsonType: 'object',
            required: ['zone_id', 'name', 'type', 'capacity'],
            properties: {
              zone_id:  { bsonType: 'long' },
              name:     { bsonType: 'string' },
              type: {
                bsonType: 'string',
                enum: ['numbered', 'general']
              },
              capacity: { bsonType: 'int' },
              tickets: {
                bsonType: ['array', 'null'],
                items: {
                  bsonType: 'object',
                  required: ['ticket_type', 'price', 'total_quantity', 'available_quantity'],
                  properties: {
                    ticket_type:        { bsonType: 'string' },
                    price:              { bsonType: 'double' },
                    total_quantity:     { bsonType: 'int' },
                    available_quantity: { bsonType: 'int' },
                    status: {
                      bsonType: 'string',
                      enum: ['available', 'sold_out', 'cancelled']
                    },
                    // perks – dane półustrukturalne
                    perks: {
                      bsonType: ['object', 'null'],
                      properties: {
                        lounge_access:   { bsonType: ['bool', 'null'] },
                        backstage_pass:  { bsonType: ['bool', 'null'] },
                        free_drink:      { bsonType: ['bool', 'null'] }
                      }
                    }
                  }
                }
              }
            }
          }
        },

        created_at: { bsonType: 'date' }
      }
    }
  },
  validationLevel:  'moderate',
  validationAction: 'warn'
});

// Indeksy
db.events.createIndex({ status: 1 },                          { name: 'idx_events_status' });
db.events.createIndex({ start_date: 1 },                      { name: 'idx_events_start_date' });
db.events.createIndex({ category: 1 },                        { name: 'idx_events_category' });
db.events.createIndex({ 'venue.city': 1 },                    { name: 'idx_events_venue_city' });
db.events.createIndex({ 'organizer.name': 1 },                { name: 'idx_events_organizer' });
db.events.createIndex({ 'additional_info.age_limit': 1 },     { name: 'idx_events_age_limit' });
db.events.createIndex({ 'zones.tickets.status': 1 },          { name: 'idx_events_ticket_status' });
db.events.createIndex({ name: 'text', description: 'text' },  { name: 'idx_events_fulltext' });

print('Kolekcja events utworzona z walidacją i indeksami.');