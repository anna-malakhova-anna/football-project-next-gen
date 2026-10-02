-- Ground truth must never be loaded into the raw schema. Returns any raw column that looks like it.
select table_name, column_name
from information_schema.columns
where table_schema = 'raw'
  and (lower(column_name) like '%true_person%' or lower(column_name) like '%ground_truth%')
union all
select table_schema || '.' || table_name, 'table named like ground truth'
from information_schema.tables
where lower(table_name) like '%person_registry%' or lower(table_name) like '%registration_truth%'
