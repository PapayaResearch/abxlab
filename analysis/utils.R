library(tidyverse)
library(stringi)
library(fixest)
library(emmeans)
library(modelsummary)
library(gt)
library(ggsci)
library(marginaleffects)
library(kableExtra)
library(showtext)

emm_options(rg.limit = 50000)

# IO Helpers --------------------------------------------------------------

create_output_dirs <- function(base_dir = "output/") {
  dirs <- c(base_dir)
  for (dir in dirs) if (!dir.exists(dir)) dir.create(dir, recursive = TRUE)
}

save_plot <- function(
    plot,
    filename,
    width = 10,
    height = 8
) {
  create_output_dirs(dirname(filename))
  showtext_auto()
  ggsave(
    filename,
    plot,
    width = width,
    height = height,
    device = cairo_pdf,
    dpi = 300
  )
}


# Tables ------------------------------------------------------------------

save_model_tables <- function(models, output_dir) {
  create_output_dirs()
  etable(
    list(
      "Main (trial FE)" = models$m1,
      "Nudge (trial FE)" = models$m2
    ),
    vcov = list(
      models$m1$vcov.scaled,
      models$m2$vcov.scaled
    ),
    file = file.path(output_dir, "main_results.tex"),
    title = "Main Results with Two-way Clustered SEs"
  )
  
  system(
    sprintf(
      "pandoc %s -o %s",
      file.path(output_dir, "main_results.tex"),
      file.path(output_dir, "main_results.html")
    )
  )
}

# Helper function for term mappings (needed for table functions)
get_term_mappings <- function(has_rating) {
  if (has_rating) {
    list(
      levels = c("Is Viewed First", "Is Cheaper", "Is Higher Rated", "Is Nudged"),
      mapping = c(
        product_position_idx = "Is Viewed First",
        product_is_higher_rated = "Is Higher Rated",
        product_is_cheaper = "Is Cheaper",
        product_is_nudged = "Is Nudged"
      )
    )
  } else {
    list(
      levels = c("Is Viewed First", "Is Cheaper", "Is Nudged"),
      mapping = c(
        product_position_idx = "Is Viewed First",
        product_is_cheaper = "Is Cheaper",
        product_is_nudged = "Is Nudged"
      )
    )
  }
}

# Generic table creation function
create_effects_table <- function(
    main_data, 
    text_data, 
    output_file,
    title = "",
    subtitle = "",
    effect_label = "Effect",
    has_rating = TRUE)
{
  
  # Get term mappings
  term_info <- get_term_mappings(has_rating)
  
  # Create main effects table
  effects_wide <- main_data %>%
    filter(term %in% names(term_info$mapping)) %>%
    select(model, term, estimate, std.error, p.value) %>%
    mutate(
      # Create significance stars
      significance = case_when(
        p.value < 0.0001 ~ "****",
        p.value < 0.001 ~ "***",
        p.value < 0.01 ~ "**",
        p.value < 0.05 ~ "*",
        TRUE ~ ""
      ),
      # Combine estimate with significance
      estimate_sig = paste0(sprintf("%.1f%%", estimate * 100), significance),
      # Clean term names for column headers
      term_clean = recode(term, !!!term_info$mapping)
    ) %>%
    select(model, term_clean, estimate_sig) %>%
    pivot_wider(
      names_from = term_clean,
      values_from = estimate_sig,
      values_fill = "—"
    )
  
  # Create the main gt table
  gt_table <- effects_wide %>%
    gt() %>%
    # Add title and subtitle
    tab_header(
      title = title,
      subtitle = subtitle
    ) %>%
    # Format column labels
    cols_label(
      model = "Model"
    ) %>%
    # Add column spanning headers
    tab_spanner(
      label = paste(effect_label, "(pp)"),
      columns = -model
    ) %>%
    # Style the table
    tab_style(
      style = cell_text(weight = "bold"),
      locations = cells_column_labels()
    ) %>%
    tab_style(
      style = cell_text(weight = "bold"),
      locations = cells_title()
    ) %>%
    # Add footnote for significance levels
    tab_footnote(
      footnote = "* p<0.05, ** p<0.01, *** p<0.001, **** p<0.0001. 
                  P-values adjusted with Benjamini-Hochberg correction.",
      locations = cells_title()
    ) %>%
    # Format table appearance
    opt_table_font(font = "Arial") %>%
    tab_options(
      table.font.size = 12,
      heading.title.font.size = 14,
      heading.subtitle.font.size = 12,
      column_labels.font.size = 11,
      table.border.top.style = "solid",
      table.border.bottom.style = "solid",
      column_labels.border.bottom.style = "solid",
      column_labels.border.top.style = "solid"
    )
  
  # Save the main table
  gt_table %>% gtsave(output_file)
  
  # Also create a LaTeX version
  latex_file <- gsub("\\.html$", ".tex", output_file)
  gt_table %>% gtsave(latex_file)
  
  # Create model X nudge text sensitivity table
  if (!is.null(text_data) && nrow(text_data) > 0) {
    nudge_text_wide <- text_data %>%
      select(nudge_text, model, estimate, std.error, p.value) %>%
      mutate(
        # Create significance stars
        significance = case_when(
          p.value < 0.0001 ~ "****",
          p.value < 0.001 ~ "***",
          p.value < 0.01 ~ "**",
          p.value < 0.05 ~ "*",
          TRUE ~ ""
        ),
        # Combine estimate with significance
        estimate_sig = paste0(sprintf("%.1f%%", estimate * 100), significance)
      ) %>%
      select(nudge_text, model, estimate_sig) %>%
      pivot_wider(
        names_from = model,
        values_from = estimate_sig,
        values_fill = "—"
      )
    
    # Create the nudge text sensitivity table
    nudge_gt_table <- nudge_text_wide %>%
      gt() %>%
      # Add title
      tab_header(
        title = "Nudge Text Sensitivity by Model",
        subtitle = paste(effect_label, "(pp)")
      ) %>%
      # Format column labels
      cols_label(
        nudge_text = "Nudge Text"
      ) %>%
      # Add column spanning headers
      tab_spanner(
        label = "Models",
        columns = -nudge_text
      ) %>%
      # Style the table
      tab_style(
        style = cell_text(weight = "bold"),
        locations = cells_column_labels()
      ) %>%
      tab_style(
        style = cell_text(weight = "bold"),
        locations = cells_title()
      ) %>%
      # Add footnote for significance levels
      tab_footnote(
        footnote = "* p<0.05, ** p<0.01, *** p<0.001, **** p<0.0001. 
                    P-values adjusted with Benjamini-Hochberg correction.",
        locations = cells_title()
      ) %>%
      # Format table appearance
      opt_table_font(font = "Arial") %>%
      tab_options(
        table.font.size = 11,
        heading.title.font.size = 14,
        heading.subtitle.font.size = 12,
        column_labels.font.size = 10,
        table.border.top.style = "solid",
        table.border.bottom.style = "solid",
        column_labels.border.bottom.style = "solid",
        column_labels.border.top.style = "solid"
      ) %>%
      # Make nudge text column wider for readability
      cols_width(
        nudge_text ~ px(300),
        everything() ~ px(80)
      )
    
    # Save the nudge text sensitivity table
    nudge_output_file <- gsub("\\.html$", "_nudge_sensitivity.html", output_file)
    nudge_gt_table %>% gtsave(nudge_output_file)
    
    # Also create LaTeX version
    nudge_latex_file <- gsub("\\.html$", "_nudge_sensitivity.tex", output_file)
    nudge_gt_table %>% gtsave(nudge_latex_file)
  }
  
  # Return the main gt object for further customization if needed
  return(gt_table)
}

# Wrapper functions for backwards compatibility
create_emmeans_table <- function(
    pp_results,
    output_file,
    title = "",
    subtitle = "",
    has_rating = TRUE)
{
  create_effects_table(
    pp_results$pp_main,
    pp_results$pp_text,
    output_file,
    title,
    subtitle,
    "Estimated Marginal Mean",
    has_rating
  )
}

create_ames_table <- function(
    ame_results,
    output_file,
    title = "",
    subtitle = "",
    has_rating = TRUE)
{
  create_effects_table(
    ame_results$ame_main,
    ame_results$ame_text,
    output_file,
    title,
    subtitle,
    "Average Marginal Effect",
    has_rating
  )
}
