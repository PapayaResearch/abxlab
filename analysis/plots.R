# Plotting Functions
# Comprehensive plotting utilities for choice analysis

# Theme and geom functions
theme_publication <- function(base_size = 12) {
  theme_light(base_size = base_size) %+replace%
    theme(
      axis.title = element_text(size = base_size, face = "bold", margin = margin(5, 5, 5, 5)),
      axis.text = element_text(size = base_size - 1),
      strip.text = element_text(size = base_size),
      strip.text.x = element_text(margin = margin(4, 4, 4, 4)),
      strip.background = element_blank(),
      panel.grid = element_blank(),
      # panel.spacing = unit(1.2, "lines"),
      legend.position = "bottom",
      legend.title = element_text(size = base_size, face = "bold"),
      legend.text = element_text(size = base_size - 1),
      legend.key.size = unit(0.8, "cm"),
      plot.background = element_rect(fill = "white", color = NA),
      plot.margin = margin(20, 20, 20, 20)
    )
}

geom_significance <- function(vjust = 0.75, hjust = -0.25, size = 3, position = "identity") {
  geom_text(
    aes(
      label = case_when(
        p.value < .0001 ~ "****",
        p.value < .001 ~ "***",
        p.value < .01 ~ "**",
        p.value < .05 ~ "*",
        TRUE ~ ""
      ),
      y = estimate + std.error * 1.96
    ),
    position = position,
    size = size,
    vjust = vjust,
    hjust = hjust,
    show.legend = FALSE,
    inherit.aes = TRUE
  )
}

# Term mapping helpers
get_term_mappings <- function(has_rating) {
  if (has_rating) {
    list(
      levels = c("Is Viewed First", "Is Cheaper", "Is Higher Rated", "Is Nudged"),
      mapping = c(
        product_position_idx = "Is Viewed First",
        product_is_higher_rated = "Is Higher Rated",
        product_is_cheaper = "Is Cheaper",
        product_is_nudged = "Is Nudged"
      ),
      labels = c(
        "Is Viewed First" = "Viewed 1st",
        "Is Cheaper" = "Cheaper", 
        "Is Higher Rated" = "Higher ★",
        "Is Nudged" = "Nudged"
      )
    )
  } else {
    list(
      levels = c("Is Viewed First", "Is Cheaper", "Is Nudged"),
      mapping = c(
        product_position_idx = "Is Viewed First",
        product_is_cheaper = "Is Cheaper",
        product_is_nudged = "Is Nudged"
      ),
      labels = c(
        "Is Viewed First" = "Viewed 1st",
        "Is Cheaper" = "Cheaper",
        "Is Nudged" = "Nudged"
      )
    )
  }
}

# Generic plot function for main effects
plot_main_effects <- function(data, output_dir, filename, ylab, has_rating = TRUE) {
  term_info <- get_term_mappings(has_rating)
  
  p <- data %>%
    mutate(
      outcome = recode(term, !!!term_info$mapping) %>%
        factor(levels = term_info$levels)
    ) %>%
    ggplot(aes(
      x = reorder(model, ifelse(model == "Human", -Inf, estimate)),
      y = estimate,
      ymin = estimate - 1.96 * std.error,
      ymax = estimate + 1.96 * std.error,
      color = (1 - p.value) * sign(estimate)
    )) +
    geom_pointrange(size = 0.3) +
    geom_hline(yintercept = 0, linetype = "dashed") +
    facet_wrap(~ outcome, nrow = 1) +
    geom_significance(vjust = 0.75, hjust = -0.25, size = 3) +
    scale_y_continuous(labels = scales::percent, expand = c(0, 0.4)) +
    scale_color_gradient2(low = "royalblue", mid = "gray50", high = "red", guide = "none") +
    coord_flip() +
    xlab("Model") +
    ylab(ylab) +
    theme_publication()
  
  file <- file.path(output_dir, filename)
  save_plot(p, file, 10, 4)
}

# Generic plot function for text effects
plot_text_effects <- function(data, data_agg, output_dir, filename_base, ylab) {
  # Faceted plot
  p1 <- data %>%
    ggplot(aes(
      x = reorder(nudge_text, estimate),
      y = estimate,
      ymin = estimate - 1.96 * std.error,
      ymax = estimate + 1.96 * std.error,
      color = (1 - p.value) * sign(estimate))
    ) +
    geom_pointrange(size = 0.3) +
    geom_hline(yintercept = 0, linetype = "dashed") +
    facet_wrap(~ reorder(model, ifelse(model == "Human", Inf, -estimate)), ncol = 6) +
    geom_significance(vjust = 0.75, hjust = -0.75, size = 3) +
    scale_y_continuous(labels = scales::percent, expand = c(0, 0.5)) +
    scale_color_gradient2(low = "royalblue", mid = "gray50", high = "red", guide = "none") +
    coord_flip() +
    xlab("Nudge Text") +
    ylab(ylab) +
    theme_publication() +
    theme(
      strip.text = element_text(size = 9),
      axis.text.x = element_text(size = 8, angle = 45, hjust = 1)
    )
  
  filename <- paste0(filename_base, "_faceted.pdf")
  file <- file.path(output_dir, filename)

  save_plot(p1, file, 14, 8)
  
  # Aggregated plot
  if (!is.null(data_agg)) {
    p2 <- data_agg %>%
      ggplot(aes(
        x = reorder(nudge_text, estimate),
        y = estimate,
        ymin = estimate - 1.96 * std.error,
        ymax = estimate + 1.96 * std.error,
        color = (1 - p.value) * sign(estimate))
      ) +
      geom_pointrange(size = 0.5) +
      geom_hline(yintercept = 0, linetype = "dashed") +
      geom_significance(vjust = 0.75, hjust = -0.25, size = 3) +
      scale_y_continuous(labels = scales::percent, expand = c(0, 0.4)) +
      scale_color_gradient2(low = "royalblue", mid = "gray50", high = "red", guide = "none") +
      coord_flip() +
      xlab("Nudge Text") +
      ylab(ylab) +
      theme_publication()
    
    filename <- paste0(filename_base, "_aggregated.pdf")
    file <- file.path(output_dir, filename)
    
    save_plot(p2, file, 8, 6)
  }
}

# Generic plot function for category effects
plot_category_effects <- function(data, output_dir, filename, ylab) {
  p <- data %>%
    ggplot(aes(
      x = reorder(category, estimate),
      y = estimate,
      ymin = estimate - 1.96 * std.error,
      ymax = estimate + 1.96 * std.error,
      color = (1 - p.value) * sign(estimate))
    ) +
    geom_pointrange(size = 0.3) +
    geom_hline(yintercept = 0, linetype = "dashed") +
    geom_significance(vjust = 0.75, hjust = -0.25, size = 2.5) +
    scale_y_continuous(labels = scales::percent, expand = c(0, 0.3)) +
    scale_color_gradient2(low = "royalblue", mid = "gray50", high = "red", guide = "none") +
    coord_flip() +
    xlab("Product Category") +
    ylab(ylab) +
    theme_publication() +
    theme(strip.text = element_text(size = 10), axis.text.y = element_text(size = 8))
  
  file <- file.path(output_dir, filename)
  save_plot(p, file, 8, 6)
}

# Steps distribution plot
plot_steps_distribution <- function(d, output_dir = "output/plots/", filename = "steps_distribution.pdf", width = 12, height = 8) {
  # Create long format data for step analysis
  d_long <- d %>%
    select(model, trial_id, paste0("step_", 1:10, ".url")) %>%
    pivot_longer(
      cols = paste0("step_", 1:10, ".url"),
      names_to = "step_name", 
      values_to = "step_url"
    ) %>%
    filter(step_url != "") %>%
    mutate(
      step_number = as.integer(gsub("step_(\\d+)\\.url", "\\1", step_name))
    )
  
  # Calculate max steps per trial
  max_steps_summary <- d_long %>%
    group_by(model, trial_id) %>%
    summarize(
      max_step = max(step_number),
      .groups = "drop"
    ) %>%
    group_by(model, max_step) %>%
    summarize(
      n = n(),
      .groups = "drop"
    )
  
  # Create the plot
  p <- max_steps_summary %>%
    ggplot(aes(x = max_step, y = n)) + 
    geom_col(fill = "steelblue", alpha = 0.8) +
    facet_wrap(~ model, ncol = 6) +
    scale_x_continuous(
      breaks = 1:10,
      labels = 1:10,
      name = "Maximum Step Reached"
    ) +
    scale_y_continuous(
      expand = expansion(mult = c(0, 0.1)),
      name = "Number of Trials"
    ) +
    theme_publication() +
    theme(
      strip.text = element_text(size = 10)
    )
  
  file <- file.path(output_dir, filename)
  save_plot(p, file, width, height)
  
  # Return the plot object for further customization if needed
  return(p)
}

# Combined analysis plots
create_combined_main_effects_plot <- function(pp_main_all, output_dir = "output/combined/") {
  term_info <- get_term_mappings(TRUE)
  
  plot_main <- pp_main_all %>%
    ggplot(aes(
      x = model,
      y = estimate,
      ymin = estimate - 1.96 * std.error,
      ymax = estimate + 1.96 * std.error,
      color = (1 - p.value) * sign(estimate)
    )) +
    geom_point(size = 0.6, position = position_dodge(width = 0.8)) +
    geom_errorbar(
      aes(ymin = estimate - 1.96 * std.error, ymax = estimate + 1.96 * std.error),
      width = 0.2, size = 0.3, alpha = 0.6, position = position_dodge(width = 0.8)
    ) +
    geom_hline(yintercept = 0, linetype = "dashed", color = "gray50", linewidth = 0.3) +
    ggh4x::facet_nested(
      ~ Experiment + outcome,
      scales = "free",
      nest_line = TRUE,
      solo_line = TRUE,
      labeller = labeller(outcome = term_info$labels, Experiment = label_value)
    ) +
    scale_y_continuous(
      labels = scales::percent,
      breaks = c(-0.5, 0.0, 0.5, 1),
      limits = c(NA, 1)
    ) +
    scale_color_gradient2(low = "royalblue", mid = "gray50", high = "red", guide = "none") +
    coord_flip() +
    xlab("Model") +
    ylab("Estimated Effect (95% CI)") +
    theme_minimal() +
    theme(
      panel.background = element_rect(fill = "white", color = "gray40"),
      panel.grid = element_blank(),
      panel.grid.major.x = element_line(color = "gray90", linewidth = 0.2),
      panel.spacing = unit(0.2, "lines"),
      axis.title = element_text(size = 8),
      strip.text = element_text(size = 8),
      axis.text = element_text(size = 8),
      axis.text.x = element_text(size = 8, angle = 45, hjust = 1)
    )
  
  # Print and save plot
  print(plot_main)
  create_output_dirs(output_dir)
  
  file <- file.path(output_dir, "main_effects_plot.pdf")
  save_plot(plot_main, file, 7.4, 2.8)
  
  return(plot_main)
}

create_combined_text_effects_plot <- function(pp_text_agg_all, output_dir = "output/combined/") {
  plot_text_agg <- pp_text_agg_all %>%
    ggplot(aes(
      x = reorder(nudge_text, estimate),
      y = estimate,
      ymin = estimate - 1.96 * std.error,
      ymax = estimate + 1.96 * std.error,
      color = (1 - p.value) * sign(estimate)
    )) +
    geom_point(size = 1, position = position_dodge(width = 0.8)) +
    geom_errorbar(
      aes(ymin = estimate - 1.96 * std.error, ymax = estimate + 1.96 * std.error),
      width = 0.2, size = 0.3, alpha = 0.6, position = position_dodge(width = 0.8)
    ) +
    geom_significance() +
    geom_hline(yintercept = 0, linetype = "dashed", color = "gray50", linewidth = 0.3) +
    facet_wrap(~ Experiment) +
    scale_y_continuous(
      labels = scales::percent,
      breaks = c(-0.5, 0.0, 0.5, 1),
      limits = c(NA, 1)
    ) +
    scale_color_gradient2(low = "royalblue", mid = "gray50", high = "red", guide = "none") +
    coord_flip() +
    xlab("Nudge") +
    ylab("Estimated Effect (95% CI)") +
    theme_minimal() +
    theme(
      panel.background = element_rect(fill = "white", color = "gray40"),
      panel.grid = element_blank(),
      panel.grid.major.x = element_line(color = "gray90", linewidth = 0.2),
      panel.spacing = unit(0.2, "lines"),
      axis.title = element_text(size = 8),
      strip.text = element_text(size = 8),
      axis.text = element_text(size = 8),
      axis.text.x = element_text(size = 8, angle = 45, hjust = 1)
    )
  
  # Print and save plot
  print(plot_text_agg)
  create_output_dirs(output_dir)

  file <- file.path(output_dir, "text_agg_effects_plot.pdf")
  save_plot(plot_text_agg, file, 7.4, 2.8)
  
  return(plot_text_agg)
}

create_combined_category_effects_plot <- function(pp_cat_all, output_dir = "output/combined/") {
  plot_cat <- pp_cat_all %>%
    ggplot(aes(
      x = reorder(category, estimate),
      y = estimate,
      ymin = estimate - 1.96 * std.error,
      ymax = estimate + 1.96 * std.error,
      color = (1 - p.value) * sign(estimate)
    )) +
    geom_point(size = 1, position = position_dodge(width = 0.8)) +
    geom_errorbar(
      aes(ymin = estimate - 1.96 * std.error, ymax = estimate + 1.96 * std.error),
      width = 0.2, size = 0.3, alpha = 0.6, position = position_dodge(width = 0.8)
    ) +
    geom_significance() +
    geom_hline(yintercept = 0, linetype = "dashed", color = "gray50", linewidth = 0.3) +
    facet_wrap(~ Experiment, nrow = 1) +
    scale_y_continuous(
      labels = scales::percent,
      breaks = c(-0.5, 0.0, 0.5, 1),
      limits = c(NA, 1)
    ) +
    scale_color_gradient2(low = "royalblue", mid = "gray50", high = "red", guide = "none") +
    coord_flip() +
    xlab("Category") +
    ylab("Estimated Effect (95% CI)") +
    theme_minimal() +
    theme(
      panel.background = element_rect(fill = "white", color = "gray40"),
      panel.grid = element_blank(),
      panel.grid.major.x = element_line(color = "gray90", linewidth = 0.2),
      panel.spacing = unit(0.2, "lines"),
      axis.title = element_text(size = 8),
      strip.text = element_text(size = 8),
      axis.text = element_text(size = 8),
      axis.text.x = element_text(size = 8, angle = 45, hjust = 1)
    )
  
  # Print and save plot
  print(plot_cat)
  create_output_dirs(output_dir)
  
  file <- file.path(output_dir, "category_effects_plot.pdf")
  save_plot(plot_cat, file, 7.4, 2.8)
  
  return(plot_cat)
}

# User profile plot
create_user_profile_plot <- function(main_effects, output_dir = "output/profile/") {
  term_info <- get_term_mappings(TRUE)
  
  plot <- main_effects %>%
    subset(term != "Is Viewed First") %>%
    ggplot(aes(
      model,
      estimate,
      ymin = estimate - 1.96 * std.error,
      ymax = estimate + 1.96 * std.error,
      color = (1 - p.value) * sign(estimate)
    )) +
    geom_point(size = 0.6, position = position_dodge(width = 0.8)) +
    geom_errorbar(
      aes(ymin = estimate - 1.96 * std.error, ymax = estimate + 1.96 * std.error),
      width = 0.2, size = 0.3, alpha = 0.6, position = position_dodge(width = 0.8)
    ) +
    geom_significance() +
    geom_hline(yintercept = 0, linetype = "dashed", color = "gray50", linewidth = 0.3) +
    geom_hline(yintercept = 1, linetype = "solid", color = "darkred", linewidth = 0.2) +
    ggh4x::facet_nested(
      term ~ profile_variable + profile_sensitivity,
      scales = "free",
      as.table = FALSE,
      nest_line = TRUE,
      solo_line = TRUE,
      labeller = labeller(term = term_info$labels, profile_variable = label_value),
      render_empty = FALSE
    ) +
    scale_y_continuous(
      labels = scales::percent,
      breaks = c(-0.5, 0.0, 0.5, 1),
      expand = expansion(mult = c(0.05, 0.34))
    ) +
    scale_color_gradient2(low = "royalblue", mid = "gray50", high = "red", guide = "none") +
    coord_flip() +
    xlab("Model") +
    ylab("Estimated Effect (95% CI)") +
    theme_publication() +
    theme(
      axis.text.x = element_text(size = 8, angle = 45, hjust = 1)
    )
  
  # Create output directory and save
  create_output_dirs(output_dir)
  
  file <- file.path(output_dir, "user_profile_effects.pdf")
  save_plot(plot, file, 12, 6)
  
  return(plot)
}

# Independent analysis plot
create_independent_effects_plot <- function(price_and_rating_effects, output_dir = "output/independent/") {
  plot <- price_and_rating_effects %>%
    ggplot(aes(
      x = model,
      y = estimate,
      ymin = estimate - 1.96 * std.error,
      ymax = estimate + 1.96 * std.error,
      color = (1 - p.value) * sign(estimate)
    )) +
    geom_point(size = 1, position = position_dodge(width = 0.8)) +
    geom_errorbar(
      aes(ymin = estimate - 1.96 * std.error, ymax = estimate + 1.96 * std.error),
      width = 0.2, size = 0.4, alpha = 0.6, position = position_dodge(width = 0.8)
    ) +
    geom_significance() +
    geom_hline(yintercept = 0, linetype = "dashed", color = "gray50", linewidth = 0.3) +
    facet_wrap(~ effect_type, nrow = 1, scales = "free") +
    scale_y_continuous(
      labels = scales::percent,
      expand = expansion(mult = c(0.05, 0.4))
    ) +
    scale_color_gradient2(low = "royalblue", mid = "gray50", high = "red", guide = "none") +
    coord_flip() +
    xlab("Model") +
    ylab("Estimated Effect (95% CI)") +
    theme_minimal() +
    theme(
      panel.grid = element_blank(),
      panel.border = element_rect(fill = NA, color = "gray40")
    )
  
  # Create output directory and save
  create_output_dirs(output_dir)

  file <- file.path(output_dir, "independent_effects.pdf")
  save_plot(plot, file, 6, 2.4)
  
  return(plot)
}

# create_price_sensitivity_plot <- function(d, output_dir = "output/independent/") {
#   # Filter to cases where product is cheaper
#   d_price <- d %>%
#     subset(product_is_cheaper == 1) %>%
#     mutate(
#       other_price = (avg_price * 2) - price,
#       price_advantage = (other_price - price) / other_price
#     )
#   
#   price_model <- feols(
#     chose_product ~ (model + product_is_nudged + product_is_higher_rated + product_position_idx + splines::ns(price_advantage, 4))^3,
#     vcov = ~ category,
#     data = d_price
#   )
#   
#   # Create prediction data for plotting
#   price_range <- seq(0.05, 1.0, by = 0.02)
#   models <- unique(d_price$model)
#   
#   pred_data <- expand.grid(
#     price_advantage = price_range,
#     model = models,
#     stringsAsFactors = FALSE
#   ) %>%
#     mutate(
#       product_is_nudged = 0,  # Set to baseline
#       product_position_idx = 0,  # Set to baseline
#       product_is_higher_rated = 0,
#       trial_id = NA,
#       category = "Electronics"  # Set to reference category
#     )
#   
#   # Generate predictions
#   pred_data$predicted <- predict(price_model, newdata = pred_data)
#   pred_data$se <- predict(price_model, newdata = pred_data, se.fit = TRUE)$se.fit
#   pred_data$lci <- pred_data$predicted - 1.96 * pred_data$se
#   pred_data$uci <- pred_data$predicted + 1.96 * pred_data$se
#   
#   plot <- pred_data %>%
#     ggplot(aes(x = price_advantage, y = predicted, color = model, group = model)) +
#     geom_line(size = 1) +
#     geom_point() +
#     geom_ribbon(aes(ymin = lci, ymax = uci, fill = model), alpha = 0.2, color = NA) +
#     geom_hline(yintercept = 0.5, linetype = "dashed", color = "red") +
#     scale_x_continuous(
#       breaks = seq(0.1, 0.9, by = 0.2),
#       expand = c(0, 0),
#       labels = c("10%", "30%", "50%", "70%", "90%")
#     ) +
#     scale_y_continuous(
#       labels = scales::percent_format(accuracy = 1),
#       limits = c(0, NA)
#     ) +
#     xlab("Price Advantage (%)") +
#     ylab("Pred. P(Choice)") +
#     scale_color_uchicago() +
#     scale_fill_uchicago() +
#     guides(
#       color = guide_legend(title = "Model"),
#       fill = guide_legend(title = "Model")
#     ) +
#     theme_publication() +
#     theme(
#       legend.position = "bottom"
#     )
#   
#   # Create output directory and save
#   create_output_dirs(output_dir)
#   
#   ggsave(
#     filename = file.path(output_dir, "price_sensitivity_model_based.pdf"),
#     width = 8,
#     height = 4,
#     plot = plot
#   )
#   
#   # Return both plot and model for further analysis if needed
#   return(list(plot = plot, model = price_model))
# }

create_price_sensitivity_plot <- function(d, output_dir = "output/independent/") {
  # Filter to cases where product is cheaper
  d_price <- d %>%
    subset(product_is_cheaper == 1) %>%
    mutate(
      other_price = (avg_price * 2) - price,
      price_advantage = (other_price - price) / other_price
    )
  
  price_model <- feols(
    chose_product ~ (model * product_is_nudged * product_is_higher_rated * product_position_idx * poly(price_advantage, 4)),
    vcov = ~ category,
    data = d_price
  )
  
  # Create prediction data for plotting
  price_range <- seq(0, 1.0, by = 0.05)
  models <- unique(d_price$model)
  
  pred_data <- price_model %>% avg_predictions(
    variables = list(
      price_advantage = price_range,
      model = models
    ),
    vcov = FALSE
  )
  
  plot <- pred_data %>%
    ggplot(aes(x = price_advantage, y = estimate, color = model, group = model)) +
    geom_line(size = 1) +
    geom_point() +
    # geom_ribbon(aes(ymin = lci, ymax = uci, fill = model), alpha = 0.2, color = NA) +
    geom_hline(yintercept = 0.5, linetype = "dashed", color = "red") +
    scale_x_continuous(
      breaks = seq(0.1, 0.9, by = 0.2),
      expand = c(0, 0),
      labels = c("10%", "30%", "50%", "70%", "90%")
    ) +
    scale_y_continuous(labels = scales::percent_format(accuracy = 1)) +
    xlab("Price Advantage (%)") +
    ylab("Pred. P(Choice)") +
    scale_color_uchicago() +
    scale_fill_uchicago() +
    guides(color = guide_legend(title = "Model", nrow = 1)) +
    theme_publication() +
    theme(
      legend.position = "bottom"
    )
  
  # Create output directory and save
  create_output_dirs(output_dir)
  
  file <- file.path(output_dir, "price_sensitivity.pdf")
  save_plot(plot, file, 10, 6)
}

# Wrapper functions for backwards compatibility
plot_ames_main <- function(ame_main, output_dir, has_rating = TRUE) {
  plot_main_effects(ame_main, output_dir, "average_marginal_effects_main.pdf", "Average Marginal Effect (pp)", has_rating)
}

plot_ames_text_model <- function(ame_text, output_dir, ame_text_agg = NULL) {
  plot_text_effects(ame_text, ame_text_agg, output_dir, "nudge_ames_by_text", "Average Marginal Effect (pp)")
}

plot_ames_category <- function(ame_cat, output_dir) {
  plot_category_effects(ame_cat, output_dir, "nudge_ames_by_category.pdf", "Average Marginal Effect (pp)")
}

plot_effects_main <- function(pp_main, output_dir, has_rating = TRUE) {
  plot_main_effects(pp_main, output_dir, "marginal_effects_main.pdf", "Estimated Marginal Mean (pp)", has_rating)
}

plot_effects_text_model <- function(pp_text, output_dir, pp_text_agg = NULL) {
  plot_text_effects(pp_text, pp_text_agg, output_dir, "nudge_effects_by_text", "Estimated Marginal Mean (pp)")
}

plot_effects_category <- function(pp_cat, output_dir) {
  plot_category_effects(pp_cat, output_dir, "nudge_effects_by_category.pdf", "Estimated Marginal Mean (pp)")
}
