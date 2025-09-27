# Marginal Effects Computation Functions
# Functions for computing estimated marginal means (EMM) and average marginal effects (AME)

# Helper functions
get_baseline_conditions <- function(has_rating, drop_rating = FALSE) {
  if (has_rating && !drop_rating) {
    list(
      product_is_cheaper = 0,
      product_is_nudged = 0,
      product_is_higher_rated = 0,
      product_position_idx = 0
    )
  } else {
    list(
      product_is_cheaper = 0,
      product_is_nudged = 0,
      product_position_idx = 0
    )
  }
}

get_variable_list <- function(has_rating, drop_rating = FALSE) {
  vars <- c("product_position_idx", "product_is_cheaper", "product_is_nudged")
  if (has_rating && !drop_rating) {
    vars <- c(vars, "product_is_higher_rated")
  }
  vars
}

# Subsample data for faster AME computation
subsample_for_ame <- function(data, max_rows = 5000) {
  if (nrow(data) <= max_rows) return(data)
  
  # Stratified sampling to maintain balance across key variables
  data %>%
    group_by(model, has_nudge, category) %>%
    slice_sample(prop = max_rows / nrow(data)) %>%
    ungroup()
}

# Compute estimated marginal means
compute_emmeans <- function(models, data, data_n, drop_rating = FALSE) {
  m1 <- models$m1
  m2 <- models$m2
  has_rating <- models$has_rating
  data_n_modelsonly <- data_n %>% subset(model != "Human") %>% droplevels()
  
  baseline_conditions <- get_baseline_conditions(has_rating, drop_rating)
  variables <- get_variable_list(has_rating, drop_rating)
  
  # Main effects for m1
  main_effects <- map_dfr(variables[variables != "product_is_nudged"], function(var) {
    emm <- emmeans(
      m1,
      specs = as.formula(paste("~", var, "| model")),
      data = data,
      weights = "proportional",
      nuisance = c("category", "nudge_text"),
      vcov. = m1$vcov.scaled
    )
    
    contrast(emm, method = list("1 - 0" = c(-1, 1))) %>%
      summary(infer = c(TRUE, TRUE), adjust = "BH") %>%
      as_tibble() %>%
      transmute(
        model,
        estimate = estimate,
        std.error = SE,
        p.value = p.value,
        term = var,
        panel = "Overall by model (EMM)"
      )
  })
  
  # Nudge effect from m2
  emm_nudge_m2 <- emmeans(
    m2,
    specs = ~ product_is_nudged | model,
    data = data_n,
    weights = "proportional",
    nuisance = c("category", "nudge_text"),
    vcov. = m2$vcov.scaled
  )
  
  pp_nudge_m2 <- contrast(
    emm_nudge_m2,
    method = list("1 - 0" = c(-1, 1))
  ) %>%
    summary(infer = c(TRUE, TRUE), adjust = "BH") %>%
    as_tibble() %>%
    transmute(
      model,
      estimate = estimate,
      std.error = SE,
      p.value = p.value,
      term = "product_is_nudged",
      panel = "Overall by model (EMM)"
    )
  
  pp_main <- bind_rows(main_effects, pp_nudge_m2)
  
  # Category effects - refit m2 with models-only data
  m2_modelsonly <- feols(
    fml = formula(m2),
    data = data_n_modelsonly,
    vcov = eval(m2$call$vcov)
  )
  
  emm_cat <- emmeans(
    m2_modelsonly,
    specs = ~ product_is_nudged | category,
    data = data_n_modelsonly,
    weights = "proportional",
    nuisance = c("model", "nudge_text"),
    vcov. = m2_modelsonly$vcov.scaled
  )
  
  pp_cat_nudge <- contrast(
    emm_cat,
    method = list("1 - 0" = c(-1, 1))
  ) %>%
    summary(infer = c(TRUE, TRUE), adjust = "BH") %>%
    as_tibble() %>%
    transmute(
      category,
      estimate = estimate,
      std.error = SE,
      p.value = p.value,
      term = "product_is_nudged",
      panel = "Nudge by Category (EMM)"
    )
  
  # Text effects
  emm_text <- emmeans(
    m2,
    specs = ~ product_is_nudged | nudge_text + model,
    data = data_n,
    weights = "proportional",
    nuisance = c("category"),
    vcov. = m2$vcov.scaled
  )
  
  pp_text <- contrast(
    emm_text,
    method = list("1 - 0" = c(-1, 1))
  ) %>%
    summary(infer = c(TRUE, TRUE), adjust = "BH") %>%
    as_tibble() %>%
    transmute(
      nudge_text,
      model,
      estimate = estimate,
      std.error = SE,
      p.value = p.value,
      term = "product_is_nudged",
      panel = "Nudge × Model (EMM)"
    )
  
  # Text effects aggregated - refit m2 with models-only data
  m2_modelsonly_text <- feols(
    fml = formula(m2),
    data = data_n_modelsonly,
    vcov = eval(m2$call$vcov)
  )
  
  emm_text_agg <- emmeans(
    m2_modelsonly_text,
    specs = ~ product_is_nudged | nudge_text,
    data = data_n_modelsonly,
    weights = "proportional",
    nuisance = c("category"),
    vcov. = m2_modelsonly_text$vcov.scaled
  )
  
  pp_text_agg <- contrast(
    emm_text_agg,
    method = list("1 - 0" = c(-1, 1))
  ) %>%
    summary(infer = c(TRUE, TRUE), adjust = "BH") %>%
    as_tibble() %>%
    transmute(
      nudge_text,
      estimate = estimate,
      std.error = SE,
      p.value = p.value,
      term = "product_is_nudged",
      panel = "Nudge Text Aggregated (EMM)"
    )
  
  list(
    pp_main = pp_main,
    pp_cat = pp_cat_nudge,
    pp_text = pp_text,
    pp_text_agg = pp_text_agg,
    has_rating = has_rating
  )
}

# Compute average marginal effects
compute_ames <- function(models, data, data_n, drop_rating = FALSE, subsample_n = 5000) {
  m1 <- models$m1
  m2 <- models$m2
  has_rating <- models$has_rating
  
  # Subsample data for faster computation
  data_sub <- subsample_for_ame(data, subsample_n)
  data_n_sub <- subsample_for_ame(data_n, subsample_n)
  
  variables <- get_variable_list(has_rating, drop_rating)
  
  # Main effects for m1
  main_effects <- map_dfr(variables[variables != "product_is_nudged"], function(var) {
    avg_slopes(
      m1,
      variables = var,
      by = "model",
      vcov = m1$vcov.scaled,
      newdata = data_sub
    ) %>%
      as_tibble() %>%
      mutate(
        p.value = 2 * (1 - pnorm(abs(statistic))),
        term = var,
        panel = "Overall by model (AME)"
      )
  })
  
  # Nudge effect from m2
  ame_nudge_m2 <- avg_slopes(
    m2,
    variables = "product_is_nudged",
    by = "model",
    vcov = m2$vcov.scaled,
    newdata = data_n_sub
  ) %>%
    as_tibble() %>%
    mutate(
      p.value = 2 * (1 - pnorm(abs(statistic))),
      term = "product_is_nudged",
      panel = "Overall by model (AME)"
    )
  
  ame_main <- bind_rows(main_effects, ame_nudge_m2) %>%
    mutate(p.value = p.adjust(p.value, method = "BH"))
  
  # Category effects
  ame_cat_nudge <- avg_slopes(
    m2,
    variables = "product_is_nudged",
    by = "category",
    vcov = m2$vcov.scaled,
    newdata = data_n_sub
  ) %>%
    as_tibble() %>%
    mutate(
      p.value = 2 * (1 - pnorm(abs(statistic))),
      term = "product_is_nudged",
      panel = "Nudge by Category (AME)"
    ) %>%
    mutate(p.value = p.adjust(p.value, method = "BH"))
  
  # Text effects
  ame_text_raw <- avg_slopes(
    m2,
    variables = "product_is_nudged",
    by = c("nudge_text", "model"),
    vcov = m2$vcov.scaled,
    newdata = data_n_sub
  ) %>%
    as_tibble() %>%
    mutate(
      p.value = 2 * (1 - pnorm(abs(statistic))),
      term = "product_is_nudged",
      panel = "Nudge × Model (AME)"
    )
  
  # Handle the grouping variables - they might be separate columns already
  if (all(c("nudge_text", "model") %in% names(ame_text_raw))) {
    ame_text <- ame_text_raw %>%
      mutate(p.value = p.adjust(p.value, method = "BH"))
  } else if ("by" %in% names(ame_text_raw)) {
    ame_text <- ame_text_raw %>%
      separate(by, into = c("nudge_text", "model"), sep = ", ") %>%
      mutate(p.value = p.adjust(p.value, method = "BH"))
  } else {
    stop("Unexpected column structure from avg_slopes()")
  }
  
  # Text effects aggregated
  ame_text_agg <- avg_slopes(
    m2,
    variables = "product_is_nudged",
    by = "nudge_text",
    vcov = m2$vcov.scaled,
    newdata = data_n_sub
  ) %>%
    as_tibble() %>%
    mutate(
      p.value = 2 * (1 - pnorm(abs(statistic))),
      term = "product_is_nudged",
      panel = "Nudge Text Aggregated (AME)"
    ) %>%
    mutate(p.value = p.adjust(p.value, method = "BH"))
  
  list(
    ame_main = ame_main,
    ame_cat = ame_cat_nudge,
    ame_text = ame_text,
    ame_text_agg = ame_text_agg,
    has_rating = has_rating
  )
}

# Compute user profile effects using emmeans
compute_user_profile_effects <- function(models) {
  variables <- get_variable_list(TRUE, FALSE)
  
  # Main effects (excluding nudge)
  main_effects <- map_dfr(variables[variables != "product_is_nudged"], function(var) {
    emm <- emmeans(
      models$m1,
      specs = as.formula(paste("~", var, "| model + profile_variable + profile_sensitivity")),
      data = models$d_c,
      weights = "proportional",
      nuisance = c("category"),
      vcov. = models$m1$vcov.scaled
    )
    
    contrast(emm, method = list("1 - 0" = c(-1, 1))) %>%
      summary(infer = c(TRUE, TRUE), adjust = "BH") %>%
      as_tibble() %>%
      transmute(
        model,
        profile_variable = profile_variable,
        profile_sensitivity = profile_sensitivity,
        estimate = estimate,
        std.error = SE,
        p.value = p.value,
        term = var,
        panel = "Overall by model (EMM)"
      )
  })
  
  # Nudge effects
  nudge_effects <- map_dfr(variables, function(var) {
    emm <- emmeans(
      models$m2,
      specs = as.formula(paste("~", var, "| model + profile_sensitivity")),
      data = models$d_n,
      weights = "proportional",
      nuisance = c("category"),
      vcov. = models$m2$vcov.scaled
    )
    
    contrast(emm, method = list("1 - 0" = c(-1, 1))) %>%
      summary(infer = c(TRUE, TRUE), adjust = "BH") %>%
      as_tibble() %>%
      transmute(
        model,
        profile_sensitivity = profile_sensitivity,
        estimate = estimate,
        std.error = SE,
        p.value = p.value,
        term = var,
        panel = "Overall by model (EMM)"
      )
  })
  
  # Combine effects
  combined_effects <- main_effects %>% 
    bind_rows(
      nudge_effects %>% mutate(
        profile_variable = "Authority Nudge"
      )
    )
  
  return(combined_effects)
}

# Compute independent analysis marginal effects
compute_independent_effects <- function(models) {
  # Price effects
  price_effects <- models$price_model %>% 
    avg_slopes(
      variables = "price_diff_pct",
      by = "model"
    ) %>%
    as_tibble() %>%
    mutate(
      p.value = 2 * (1 - pnorm(abs(statistic))),
      effect_type = "Price AME (100pp change)"
    )
  
  # Rating effects
  rating_effects <- models$rating_model %>% 
    avg_slopes(
      variables = "rating_diff",
      by = "model"
    ) %>%
    as_tibble() %>%
    mutate(
      p.value = 2 * (1 - pnorm(abs(statistic))),
      effect_type = "Rating AME (1-point change)"
    )
  
  # Combine and adjust p-values
  combined_effects <- bind_rows(price_effects, rating_effects) %>%
    mutate(p.value = p.adjust(p.value, method = "BH"))
  
  return(combined_effects)
}
