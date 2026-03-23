-- Confirm the recreated cluster still matches the validated environment.

SELECT extversion
FROM pg_extension
WHERE extname = 'google_ml_integration';

SELECT extversion
FROM pg_extension
WHERE extname = 'vector';

SELECT name, setting
FROM pg_settings
WHERE name IN (
  'google_ml_integration.enable_ai_query_engine',
  'google_ml_integration.enable_model_support'
)
ORDER BY name;

SELECT vector_dims(google_ml.embedding('text-embedding-005', 'hello world')::vector);

SELECT *
FROM google_ml.model_info_view;
