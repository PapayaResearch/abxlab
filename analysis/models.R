# Model Fitting Functions
# Functions for fitting various statistical models

# Core model fitting function
fit_models <- function(d, drop_rating = FALSE) {
  has_rating <- attr(d, "has_rating") %||% TRUE
  
  # Construct formula components based on whether rating is included
  if (has_rating && !drop_rating) {
    main_formula <- as.formula(
      "chose_product ~ (model * product_is_cheaper * product_is_nudged * product_is_higher_rated * product_position_idx) | trial_id"
    )
    nudge_formula <- as.formula(
      "chose_product ~ (model * product_is_cheaper * product_is_nudged * product_is_higher_rated * product_position_idx * nudge_text) + (product_is_nudged * category) | trial_id"
    )
  } else {
    main_formula <- as.formula(
      "chose_product ~ (model * product_is_cheaper * product_is_nudged * product_position_idx) | trial_id"
    )
    nudge_formula <- as.formula(
      "chose_product ~ (model * product_is_cheaper * product_is_nudged * product_position_idx * nudge_text) + (product_is_nudged * category) | trial_id"
    )
  }
  
  m1 <- feols(
    main_formula,
    vcov = ~ nudge_text + category,
    data = d
  )
  
  # Nudge models
  d_n <- d %>% subset(has_nudge == "Nudge") %>% droplevels()
  d_n <- droplevels(d_n)
  
  m2 <- feols(
    nudge_formula,
    vcov = ~ nudge_text + category,
    data = d_n
  )
  
  list(m1 = m1, m2 = m2, d_n = d_n, has_rating = has_rating)
}

# Fit models for user profile analysis
fit_user_profile_models <- function(d) {
  d_c <- d %>% subset(has_nudge == "No Nudge") %>% droplevels()
  
  m1 <- feols(
    chose_product ~ (model * product_is_cheaper * product_is_higher_rated * product_position_idx * profile_variable * profile_sensitivity) | trial_id,
    vcov = ~ category,
    data = d_c
  )
  
  # Nudge models
  d_n <- d %>% subset(has_nudge == "Nudge") %>% droplevels()
  
  m2 <- feols(
    chose_product ~ (model * product_is_cheaper * product_is_higher_rated * product_position_idx * profile_sensitivity * product_is_nudged) | trial_id,
    vcov = ~ category,
    data = d_n
  )
  
  list(m1 = m1, m2 = m2, d_c = d_c, d_n = d_n)
}

# Fit models for independent analysis
fit_independent_models <- function(trial_summary) {
  # Price analysis
  price_data <- trial_summary %>%
    subset(coverage_type == "price_coverage")
  
  price_lpm <- feols(
    chose_cheaper ~ log1p(price_diff_pct) * model * log(price_avg) | category,
    vcov = ~ category,
    data = price_data
  )
  
  # Rating analysis
  rating_data <- trial_summary %>%
    subset(coverage_type == "rating_coverage")
    
  rating_lpm <- feols(
    chose_higher_rated ~ rating_diff * model * rating_avg | category,
    data = rating_data
  )
  
  list(
    price_model = price_lpm,
    rating_model = rating_lpm,
    price_data = price_data,
    rating_data = rating_data
  )
}
