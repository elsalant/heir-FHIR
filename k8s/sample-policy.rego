package dataapi.authz

import data.data_policies as dp

transform[action] {
  description := "Redact sensitive columns in diabetes datasets"
  dp.AccessType() == "READ"
  dp.dataset_has_tag("health")
  column_names := dp.column_with_any_name({"Id"})
  action = dp.build_redact_column_action(column_names[_], dp.build_policy_from_description(description))
}
