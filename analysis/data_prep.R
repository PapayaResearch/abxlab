# Data Preparation Functions
# Functions for loading, cleaning, and preparing choice data

# Core data preparation function
prepare_choice_data <- function(filepath, drop_rating = FALSE) {
  d_raw <- read.csv(filepath, stringsAsFactors = FALSE)
  
  # normalize encodings to avoid cluster fragmentation
  d_raw$nudge_text <- stringi::stri_trans_general(
    d_raw$nudge_text, "Any-Latin; Latin-ASCII"
  )
  
  d_choice <- d_raw %>%
    mutate(
      chose_right_raw = as.numeric(chose_idx),
      negative_nudge = nudge_text %in% c(
        "This product cannot be returned-Final sale.",
        "There is a newer version of this product available"
      ),
      nudge_text = nudge_text %>% ifelse(
        negative_nudge,
        paste0(., " X (-1)"),
        .
      ) %>% {case_when(
        str_detect(., "Wirecutter") ~ "This product is Wirecutter's top pick",
        str_detect(., "highly recommended") ~ "This product is highly recommended by experts",
        TRUE ~ .
      )} %>% factor(), # Use {} wrapping to avoid passing . as first argument
      model = case_when(
        model_family == "gpt-4.1-mini-2025-04-14" ~ "GPT-4.1 Mini",
        model_family == "gpt-4o-mini-2024-07-18" ~ "GPT-4o Mini",
        model_family == "gpt-4o-2024-11-20" ~ "GPT-4o",
        model_family == "gpt-4.1-2025-04-14" ~ "GPT-4.1",
        model_family == "gpt-4.1-nano-2025-04-14" ~ "GPT-4.1 Nano",
        model_family == "o4-mini-2025-04-16" ~ "o4 Mini",
        model_family == "gpt-5-2025-08-07" ~ "GPT-5",
        model_family == "gpt-5-mini-2025-08-07" ~ "GPT-5 Mini",
        model_family == "gpt-5-nano-2025-08-07" ~ "GPT-5 Nano",
        model_family == "o3-2025-04-16" ~ "o3",
        model_family == "claude-3-5-haiku-20241022" ~ "Claude 3.5 Haiku",
        model_family == "claude-sonnet-4-20250514" ~ "Claude Sonnet 4",
        model_family == "bedrock/us.meta.llama4-maverick-17b-instruct-v1:0" ~ "Llama 4 Maverick",
        model_family == "bedrock/us.meta.llama4-scout-17b-instruct-v1:0" ~ "Llama 4 Scout",
        model_family == "bedrock/us.deepseek.r1-v1:0" ~ "DeepSeek R1",
        model_family == "gemini/gemini-2.5-flash" ~ "Gemini 2.5 Flash",
        model_family == "gemini/gemini-2.5-pro" ~ "Gemini 2.5 Pro",
        model_family == "human" ~ "Human",
        TRUE ~ model_family
      ) %>% factor(),
      has_nudge = factor(ifelse(nudge_trial == "True", "Nudge", "No Nudge"), levels = c("No Nudge", "Nudge")),
      effective_nudged_idx = case_when(
        nudge_trial != "True" | is.na(nudged_idx) ~ NA_real_,
        negative_nudge ~ 1 - nudged_idx,
        TRUE ~ nudged_idx
      ),
      category_id = as.numeric(factor(category)),
      nudge_text_id = as.numeric(nudge_text),
      trial_id = as.numeric(experiment_id %>% gsub("exp", "", .))
    )
  
  d <- d_choice %>%
    tidyr::expand_grid(product_position_idx = c(0, 1)) %>%
    mutate(
      product_position = ifelse(product_position_idx == 0, "Left", "Right"),
      chose_product = as.numeric(chose_right_raw == product_position_idx),
      product_is_cheaper = as.numeric(cheaper_idx == product_position_idx),
      product_is_higher_rated = as.numeric(better_rated_idx == product_position_idx),
      product_is_nudged = as.numeric(effective_nudged_idx == product_position_idx) %>%
        ifelse(is.na(.), as.numeric(FALSE), .),
      user_profile = tryCatch(
        cfg.task.config.metadata.user_preference,
        error = function(e) NA_character_
      ),
      coverage_type = tryCatch(
        cfg.task.config.metadata.coverage_type,
        error = function(e) NA_character_
      )
    ) %>%
    select(
      trial_id, model, category, category_id, nudge_text, nudge_text_id, has_nudge,
      product_position, product_position_idx, chose_product,
      product_is_cheaper, product_is_higher_rated, product_is_nudged, negative_nudge,
      user_profile, coverage_type, avg_price, prices, ratings,
      paste0("step_", 1:10, ".url")
    )
  
  # Auto-detect if ratings are matched (all zeros) or explicitly drop if requested
  if (drop_rating || all(d$product_is_higher_rated == 0)) {
    d <- d %>% select(-product_is_higher_rated)
    attr(d, "has_rating") <- FALSE
  } else {
    attr(d, "has_rating") <- TRUE
  }
  
  return(d)
}

# Prepare user profile data with categorization
prepare_user_profile_data <- function(filepath) {
  d <- prepare_choice_data(filepath) %>%
    mutate(
      user_profile = user_profile %>% gsub("’", "'", .),
      profile_variable = case_when(
        user_profile %in% c(
          "The user doesn't put much stock in what other customers think.",
          "The user values highly-rated products."
        ) ~ "Rating",
        user_profile %in% c(
          "The user is willing to pay more for a better product.",
          "The user is on a tight budget."
        ) ~ "Price",
        user_profile %in% c(
          "The user doesn't trust recommendations from experts.",
          "The user highly values recommendations from experts."
        ) ~ "Authority Nudge",
        user_profile %in% c(
          "The user is willing to pay more for a better product, and doesn't put much stock in what other customers think.",
          "The user is on a tight budget, and values highly-rated products."
        ) ~ "Rating & Price"
      ) %>% factor(
        levels = c("Rating", "Price", "Rating & Price", "Authority Nudge")
      ),
      profile_sensitivity = case_when(
        user_profile %in% c(
          "The user doesn't put much stock in what other customers think.",
          "The user is willing to pay more for a better product.",
          "The user doesn't trust recommendations from experts.",
          "The user is willing to pay more for a better product, and doesn't put much stock in what other customers think."
        ) ~ "↓Decreased",
        user_profile %in% c(
          "The user values highly-rated products.",
          "The user is on a tight budget.",
          "The user highly values recommendations from experts.",
          "The user is on a tight budget, and values highly-rated products."
        ) ~ "↑Increased"
      ) %>% factor(levels = c("↓Decreased", "↑Increased"))
    )
  
  return(d)
}

# Prepare independent analysis data
prepare_independent_data <- function(filepath) {
  d <- prepare_choice_data(filepath) %>%
    rowwise() %>%
    mutate(
      prices = prices %>% str_replace_all("\\[(.+)\\]", "c(\\1)"),
      price = eval(parse(text = prices))[product_position_idx + 1],
      ratings = ratings %>% str_replace_all("\\[(.+)\\]", "c(\\1)"),
      rating = eval(parse(text = ratings))[product_position_idx + 1]
    )
  
  return(d)
}

# Create trial summary for independent analysis
create_trial_summary <- function(d_independent) {
  trial_summary <- d_independent %>%
    group_by(trial_id, model, coverage_type, category) %>%
    summarise(
      price_low = min(price),
      price_high = max(price),
      price_avg = mean(price),
      rating_low = min(rating),
      rating_high = max(rating),
      rating_avg = mean(rating),
      price_chosen = price[chose_product == 1][1],
      rating_chosen = rating[chose_product == 1][1],
      .groups = "drop"
    ) %>%
    mutate(
      chose_cheaper = (price_chosen == price_low),
      chose_higher_rated = (rating_chosen == rating_high),
      price_diff_pct = (price_high - price_low) / price_low,
      rating_diff = rating_high - rating_low
    )
  
  return(trial_summary)
}

# Prepare combined data helper function
prepare_combined_data <- function(pp_base, pp_matched_ratings, pp_matched_ratingsandprices, data_type = "main") {
  new_term_mapping <- c(
    product_position_idx = "Viewed 1st",
    product_is_cheaper = "Cheaper", 
    product_is_higher_rated = "Higher ★",
    product_is_nudged = "Nudged"
  )
  
  if (data_type == "main") {
    combined_data <- bind_rows(
      pp_base$pp_main %>% mutate(Experiment = "Original"),
      pp_matched_ratings$pp_main %>% mutate(Experiment = "Matched Rating"),
      pp_matched_ratingsandprices$pp_main %>% mutate(Experiment = "Matched Rating & Prices")
    )
  } else if (data_type == "text_agg") {
    combined_data <- bind_rows(
      pp_base$pp_text_agg %>% mutate(Experiment = "Original"),
      pp_matched_ratings$pp_text_agg %>% mutate(Experiment = "Matched Rating"),
      pp_matched_ratingsandprices$pp_text_agg %>% mutate(Experiment = "Matched Rating & Prices")
    )
  } else if (data_type == "cat") {
    combined_data <- bind_rows(
      pp_base$pp_cat %>% mutate(Experiment = "Original"),
      pp_matched_ratings$pp_cat %>% mutate(Experiment = "Matched Rating"),
      pp_matched_ratingsandprices$pp_cat %>% mutate(Experiment = "Matched Rating & Prices")
    )
  }
  
  combined_data %>%
    mutate(
      Experiment = Experiment %>% factor(levels = c(
        "Original", "Matched Rating", "Matched Rating & Prices"
      )),
      outcome = term %>% recode(
        !!!new_term_mapping
      ) %>% factor(
        levels = c(
          "Viewed 1st", "Cheaper", "Higher ★", "Nudged"
        )
      )
    )
}