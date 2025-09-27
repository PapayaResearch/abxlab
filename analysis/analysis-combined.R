source("utils.R")
source("data_prep.R")
source("models.R")
source("marginals.R")
source("plots.R")

# Main Analysis Function -------------------------------------------------

run_analysis <- function(input_file, output_dir, drop_rating = FALSE, human_data = NULL) {
  create_output_dirs(output_dir)
  d <- prepare_choice_data(input_file, drop_rating = drop_rating)
  if (!is.null(human_data)) {
    d <- d %>% rbind(prepare_choice_data(human_data, drop_rating = drop_rating))
  }
  
  plot_steps_distribution(d, output_dir)
  
  d <- droplevels(d)
  mods <- fit_models(d, drop_rating = drop_rating)
  mods %>% save_model_tables(output_dir)
  
  # EMMs
  pp <- mods %>% compute_emmeans(
    d,
    mods$d_n,
    drop_rating = drop_rating
  )
  pp$pp_main %>% plot_effects_main(output_dir, has_rating = pp$has_rating)
  pp$pp_text %>% plot_effects_text_model(output_dir, pp_text_agg = pp$pp_text_agg)
  pp$pp_cat %>% plot_effects_category(output_dir)
  create_emmeans_table(
    pp_results = pp,
    output_file = file.path(output_dir, "emmeans_table.html"),
    title = "",
    subtitle = "",
    has_rating = pp$has_rating
  )
  
  return(pp)
}

# Run Base Analyses -------------------------------------------------------

pp_base <- run_analysis("data/combined_full.csv", "output/original/", drop_rating = FALSE, human_data = "data/study_data_all_regular_results_processed.csv")
pp_matchedratings <- run_analysis("data/combined_full-matched_ratings.csv", "output/matched-ratings/", drop_rating = TRUE)
pp_matchedratingsandprices <- run_analysis("data/combined_full-matched_ratingsandprices.csv", "output/matched-ratingsandprices/", drop_rating = TRUE)

p.attribute_effect <- pp_base$pp_main %>%
  group_by(model) %>%
  summarize(estimate = mean(abs(estimate)), .groups = "drop") %>%
  ggplot(aes(reorder(model, estimate), estimate)) +
  geom_col() +
  xlab("Model") +
  ylab("Mean Absolute Attribute Effect") +
  scale_y_continuous(labels = scales::percent_format(accuracy = 1), expand = c(0, 0)) +
  theme_publication() +
  theme(
    axis.text.x = element_text(angle = 45, hjust = 1)
  )

p.attribute_effect %>% save_plot("output/original/attribute_effects.pdf", width = 6, height = 4)

# Combined Analysis -------------------------------------------------------

# Prepare combined data
pp_main_all <- prepare_combined_data(pp_base, pp_matchedratings, pp_matchedratingsandprices, "main")
pp_text_agg_all <- prepare_combined_data(pp_base, pp_matchedratings, pp_matchedratingsandprices, "text_agg")
pp_cat_all <- prepare_combined_data(pp_base, pp_matchedratings, pp_matchedratingsandprices, "cat")

# Create combined plots
create_combined_main_effects_plot(pp_main_all)
create_combined_text_effects_plot(pp_text_agg_all)
create_combined_category_effects_plot(pp_cat_all)

# Create LaTeX table for combined results
term_info <- get_term_mappings(TRUE)
pp_main_all %>%
  mutate(
    outcome = recode(term, !!!term_info$mapping),
    outcome = factor(outcome, levels = c("Is Viewed First", "Is Higher Rated", "Is Cheaper", "Is Nudged")),
    estimate_pct = sprintf("%.1f", estimate * 100),
    significance = case_when(
      p.value < 0.0001 ~ "\\pstar{4}",
      p.value < 0.001  ~ "\\pstar{3}",
      p.value < 0.01   ~ "\\pstar{2}",
      p.value < 0.05   ~ "\\pstar{1}",
      TRUE ~ ""
    ),
    color = case_when(
      p.value < 0.05 & estimate > 0 ~ "\\textcolor{red}{",
      p.value < 0.05 & estimate < 0 ~ "\\textcolor{blue}{",
      TRUE ~ ""
    ),
    color_close = ifelse(color != "", "}", ""),
    estimate_formatted = paste0(color, estimate_pct, color_close, significance)
  ) %>%
  select(model, outcome, Experiment, estimate_formatted) %>%
  arrange(model, outcome, Experiment) %>%
  pivot_wider(
    names_from = c(outcome, Experiment),
    values_from = estimate_formatted,
    names_sep = "_",
    values_fill = list(estimate_formatted = "—")
  ) %>%
  arrange(model) %>%
  kbl(
    format = "latex",
    booktabs = TRUE,
    escape = FALSE,
    col.names = c(" ",
                  "O", "MR", "MRaP",
                  "O",
                  "O", "MR", "MRaP",
                  "O", "MR", "MRaP"),
    caption = "Estimated marginal change in probability of choosing a product (\\%).",
    label = "tab:model_results"
  ) %>%
  kable_styling(latex_options = c("hold_position", "scale_down")) %>%
  column_spec(1, bold = TRUE) %>%
  add_header_above(c(
    " " = 1,
    "Viewed 1st" = 3,
    "Higher Rated" = 1,
    "Cheaper"  = 3,
    "Nudged"      = 3
  ), escape = FALSE) %>%
  save_kable("output/combined/model_results_table.tex")

# User Profile Analysis ---------------------------------------------------

# Prepare and analyze user profile data
d_user_profiles <- prepare_user_profile_data("data/combined_full-userprofiles.csv")
models_user_profiles <- fit_user_profile_models(d_user_profiles)
user_profile_effects <- compute_user_profile_effects(models_user_profiles)

# Apply term mapping and create plot
user_profile_effects <- user_profile_effects %>% 
  mutate(
    term = term %>% recode(!!!term_info$mapping)
  )

create_user_profile_plot(user_profile_effects)

# Independent Analysis ----------------------------------------------------

# Prepare independent data
d_independent <- prepare_independent_data("data/combined_full-independent.csv")
trial_summary <- create_trial_summary(d_independent)

# Fit models and compute effects
independent_models <- fit_independent_models(trial_summary)
independent_effects <- compute_independent_effects(independent_models)

# Create plot
create_independent_effects_plot(independent_effects)
create_price_sensitivity_plot(d_independent %>% subset(coverage_type == "price_coverage"))
