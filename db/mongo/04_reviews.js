// ============================================================
// MongoDB – Kolekcja: reviews
// Plik: db/mongo/04_reviews.js
// ============================================================

db = db.getSiblingDB('eventsdb');

db.createCollection('reviews', {
  validator: {
    $jsonSchema: {
      bsonType: 'object',
      required: ['user_id', 'event_id', 'rating', 'created_at'],
      properties: {
        user_id: {
          bsonType: 'long',
          description: 'ID użytkownika – referencja do kolekcji users'
        },
        event_id: {
          bsonType: 'long',
          description: 'ID wydarzenia – referencja do kolekcji events'
        },
        rating: {
          bsonType: 'int',
          minimum: 1,
          maximum: 5,
          description: 'Ocena od 1 do 5'
        },
        comment: {
          bsonType: ['string', 'null'],
          description: 'Treść recenzji – opcjonalna'
        },
        created_at: { bsonType: 'date' }
      }
    }
  },
  validationLevel:  'moderate',
  validationAction: 'warn'
});

// Indeksy
db.reviews.createIndex({ event_id: 1 },              { name: 'idx_reviews_event' });
db.reviews.createIndex({ user_id: 1 },               { name: 'idx_reviews_user' });
db.reviews.createIndex({ rating: 1 },                { name: 'idx_reviews_rating' });
db.reviews.createIndex(
  { user_id: 1, event_id: 1 },
  { unique: true, name: 'idx_reviews_unique_user_event' }
);

print('Kolekcja reviews utworzona z walidacją i indeksami.');