// ============================================================
// MongoDB – Kolekcja: bookings
// Plik: db/mongo/03_bookings.js
// ============================================================

db = db.getSiblingDB('eventsdb');

db.createCollection('bookings', {
  validator: {
    $jsonSchema: {
      bsonType: 'object',
      required: ['user_id', 'booking_date', 'status', 'total_price', 'items'],
      properties: {
        // Referencja do users (int/long id)
        user_id: {
          bsonType: 'long',
          description: 'ID użytkownika – referencja do kolekcji users'
        },
        booking_date: { bsonType: 'date' },
        status: {
          bsonType: 'string',
          enum: ['pending', 'paid', 'cancelled']
        },
        total_price: {
          bsonType: 'double',
          minimum: 0
        },

        // Pozycje rezerwacji – denormalizowane (snapshot danych w momencie zakupu)
        items: {
          bsonType: 'array',
          minItems: 1,
          items: {
            bsonType: 'object',
            required: ['event_id', 'event_name', 'ticket_type', 'quantity', 'price_at_purchase'],
            properties: {
              event_id:          { bsonType: 'long' },
              event_name:        { bsonType: 'string' },
              ticket_type:       { bsonType: 'string' },
              zone_name:         { bsonType: ['string', 'null'] },
              quantity:          { bsonType: 'int', minimum: 1 },
              price_at_purchase: { bsonType: 'double' }
            }
          }
        },

        // Płatność wbudowana – zawsze czytana razem z rezerwacją
        payment: {
          bsonType: ['object', 'null'],
          properties: {
            method: {
              bsonType: ['string', 'null'],
              enum: ['card', 'transfer', 'blik', 'paypal', null]
            },
            amount:       { bsonType: ['double', 'null'] },
            payment_date: { bsonType: ['date', 'null'] },
            status: {
              bsonType: ['string', 'null'],
              enum: ['pending', 'completed', 'failed', 'refunded', null]
            }
          }
        },

        created_at: { bsonType: ['date', 'null'] }
      }
    }
  },
  validationLevel:  'moderate',
  validationAction: 'warn'
});

// Indeksy
db.bookings.createIndex({ user_id: 1 },                 { name: 'idx_bookings_user' });
db.bookings.createIndex({ status: 1 },                  { name: 'idx_bookings_status' });
db.bookings.createIndex({ booking_date: -1 },           { name: 'idx_bookings_date' });
db.bookings.createIndex({ 'items.event_id': 1 },        { name: 'idx_bookings_event' });
db.bookings.createIndex({ 'payment.status': 1 },        { name: 'idx_bookings_payment_status' });
db.bookings.createIndex({ user_id: 1, status: 1 },      { name: 'idx_bookings_user_status' });

print('Kolekcja bookings utworzona z walidacją i indeksami.');