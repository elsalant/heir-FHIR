package dataapi.authz

rule[{"action": {"name":"RedactColumn", "columns": column_names}, "policy": description}] {
  description := "Redact columns tagged as PII in datasets tagged with healthcare = true"
  input.resource.tags.healthcare
  column_names := [input.resource.columns[i].name | input.resource.columns[i].tags.PII]
  count(column_names) > 0
}
rule[{"action": {"name":"Statistics", "columns": column_names}, "policy": description}] {
  description := "Return statistical analysis of glucose in body volume"
  input.resource.tags.healthcare
  column_names := [input.resource.columns[i].name | input.resource.columns[i].tags.stats]
  count(column_names) > 0
}

rule[{"action": {"name":"BlockResource", "columns": column_names}, "policy": description}] {
  description := "Blocks whole resource"
  input.resource.tags.healthcare
  column_names := [input.resource.columns[i].name | input.resource.columns[i].tags.blocked]
  count(column_names) > 0
}