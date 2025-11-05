"""
Enhanced data cleaning service with intelligent outlier detection,
missing value imputation, and automated data quality assessment.
"""

import pandas as pd
import numpy as np
from sklearn.impute import KNNImputer, SimpleImputer
from sklearn.ensemble import IsolationForest
from sklearn.cluster import DBSCAN
from sklearn.preprocessing import StandardScaler, LabelEncoder
from scipy import stats
import json
import logging
from typing import Dict, Any, List, Tuple, Optional
import warnings

# Suppress warnings
warnings.filterwarnings('ignore')
logger = logging.getLogger(__name__)

class EnhancedDataCleaner:
    """Advanced data cleaning with ML-based analysis."""

    def __init__(self):
        self.cleaning_report = {}
        self.original_data = None
        self.cleaned_data = None
        self.data_types = {}
        self.missing_info = {}
        self.outlier_info = {}
        self.duplicate_info = {}

    def analyze_dataset(self, data: pd.DataFrame, target_column: str = None) -> Dict[str, Any]:
        """Comprehensive data analysis for cleaning recommendations."""
        try:
            self.original_data = data.copy()
            self.data_types = self._detect_data_types(data)

            # Basic statistics
            analysis = {
                'shape': data.shape,
                'data_types': self.data_types,
                'missing_values': self._analyze_missing_values(data),
                'duplicates': self._analyze_duplicates(data),
                'outliers': self._analyze_outliers(data),
                'data_distribution': self._analyze_distributions(data),
                'correlations': self._analyze_correlations(data),
                'target_column_analysis': None
            }

            # Target column specific analysis
            if target_column and target_column in data.columns:
                analysis['target_column_analysis'] = self._analyze_target_column(data, target_column)

            # Generate quality score
            analysis['quality_score'] = self._calculate_quality_score(analysis)

            return analysis

        except Exception as e:
            logger.error(f"Error analyzing dataset: {e}")
            raise e

    def clean_dataset(self, data: pd.DataFrame, config: Dict[str, Any] = None,
                     target_column: str = None) -> Tuple[pd.DataFrame, Dict[str, Any]]:
        """Perform comprehensive data cleaning."""
        try:
            self.original_data = data.copy()
            self.cleaned_data = data.copy()
            config = config or {}

            # Generate cleaning report
            self.cleaning_report = {
                'original_shape': data.shape,
                'steps_performed': [],
                'changes_made': {},
                'quality_improvement': {},
                'recommendations': []
            }

            # Step 1: Handle missing values
            if config.get('handle_missing', True):
                self._handle_missing_values(config.get('missing_strategy', 'auto'))

            # Step 2: Remove duplicates
            if config.get('remove_duplicates', True):
                self._remove_duplicates()

            # Step 3: Handle outliers
            if config.get('handle_outliers', True):
                self._handle_outliers(config.get('outlier_strategy', 'iqr'))

            # Step 4: Data type conversion
            if config.get('fix_data_types', True):
                self._fix_data_types()

            # Step 5: Standardize text data
            if config.get('standardize_text', True):
                self._standardize_text_columns()

            # Step 6: Feature engineering suggestions
            if config.get('suggest_features', True):
                self._generate_feature_suggestions(target_column)

            # Final quality assessment
            self._assess_cleaning_quality()

            self.cleaning_report['final_shape'] = self.cleaned_data.shape

            return self.cleaned_data, self.cleaning_report

        except Exception as e:
            logger.error(f"Error cleaning dataset: {e}")
            raise e

    def _detect_data_types(self, data: pd.DataFrame) -> Dict[str, str]:
        """Intelligently detect data types."""
        detected_types = {}

        for column in data.columns:
            if data[column].dtype == 'object':
                # Check if it's numeric
                try:
                    pd.to_numeric(data[column].dropna())
                    detected_types[column] = 'numeric'
                except:
                    # Check if it's datetime
                    try:
                        pd.to_datetime(data[column].dropna())
                        detected_types[column] = 'datetime'
                    except:
                        # Check if it's categorical (low cardinality)
                        unique_ratio = data[column].nunique() / len(data)
                        if unique_ratio < 0.1:  # Less than 10% unique values
                            detected_types[column] = 'categorical'
                        else:
                            detected_types[column] = 'text'
            else:
                detected_types[column] = str(data[column].dtype).lower()

        return detected_types

    def _analyze_missing_values(self, data: pd.DataFrame) -> Dict[str, Any]:
        """Analyze missing value patterns."""
        missing_counts = data.isnull().sum()
        missing_percentages = (missing_counts / len(data)) * 100

        missing_info = {
            'total_missing': missing_counts.sum(),
            'missing_percentage': (missing_counts.sum() / (data.shape[0] * data.shape[1])) * 100,
            'columns_with_missing': missing_counts[missing_counts > 0].to_dict(),
            'missing_percentages': missing_percentages[missing_percentages > 0].to_dict()
        }

        # Identify missing value patterns
        if missing_counts.sum() > 0:
            # Check for MCAR (Missing Completely At Random)
            missing_matrix = data.isnull()
            correlation_matrix = missing_matrix.corr()
            max_correlation = correlation_matrix.abs().max().max()

            missing_info['missing_pattern'] = {
                'max_correlation': max_correlation,
                'pattern_type': 'mcar' if max_correlation < 0.3 else 'mar_or_mnar'
            }

        return missing_info

    def _analyze_duplicates(self, data: pd.DataFrame) -> Dict[str, Any]:
        """Analyze duplicate records."""
        total_duplicates = data.duplicated().sum()

        duplicate_info = {
            'total_duplicate_rows': total_duplicates,
            'duplicate_percentage': (total_duplicates / len(data)) * 100 if len(data) > 0 else 0
        }

        if total_duplicates > 0:
            # Find duplicate rows
            duplicate_rows = data[data.duplicated(keep=False)]
            duplicate_groups = duplicate_rows.groupby(list(data.columns)).size()

            duplicate_info.update({
                'duplicate_groups': len(duplicate_groups),
                'avg_duplicates_per_group': duplicate_groups.mean(),
                'max_duplicates_in_group': duplicate_groups.max(),
                'duplicate_examples': data[data.duplicated(keep=False)].head().to_dict('records')
            })

        return duplicate_info

    def _analyze_outliers(self, data: pd.DataFrame) -> Dict[str, Any]:
        """Analyze outliers using multiple methods."""
        outlier_info = {}

        numeric_columns = data.select_dtypes(include=[np.number]).columns

        for column in numeric_columns:
            column_data = data[column].dropna()

            if len(column_data) < 4:  # Skip if too few data points
                continue

            outliers = {}

            # IQR method
            Q1 = column_data.quantile(0.25)
            Q3 = column_data.quantile(0.75)
            IQR = Q3 - Q1
            lower_bound = Q1 - 1.5 * IQR
            upper_bound = Q3 + 1.5 * IQR
            iqr_outliers = column_data[(column_data < lower_bound) | (column_data > upper_bound)]
            outliers['iqr'] = {
                'count': len(iqr_outliers),
                'percentage': (len(iqr_outliers) / len(column_data)) * 100,
                'bounds': [lower_bound, upper_bound]
            }

            # Z-score method
            z_scores = np.abs(stats.zscore(column_data))
            z_outliers = column_data[z_scores > 3]
            outliers['zscore'] = {
                'count': len(z_outliers),
                'percentage': (len(z_outliers) / len(column_data)) * 100
            }

            # Isolation Forest (if enough data)
            if len(column_data) > 50:
                try:
                    iso_forest = IsolationForest(contamination=0.1, random_state=42)
                    outlier_labels = iso_forest.fit_predict(column_data.values.reshape(-1, 1))
                    iso_outliers = column_data[outlier_labels == -1]
                    outliers['isolation_forest'] = {
                        'count': len(iso_outliers),
                        'percentage': (len(iso_outliers) / len(column_data)) * 100
                    }
                except:
                    pass

            outlier_info[column] = outliers

        return outlier_info

    def _analyze_distributions(self, data: pd.DataFrame) -> Dict[str, Any]:
        """Analyze data distributions."""
        distribution_info = {}

        numeric_columns = data.select_dtypes(include=[np.number]).columns

        for column in numeric_columns:
            column_data = data[column].dropna()

            if len(column_data) == 0:
                continue

            # Basic statistics
            stats_info = {
                'mean': float(column_data.mean()),
                'median': float(column_data.median()),
                'std': float(column_data.std()),
                'min': float(column_data.min()),
                'max': float(column_data.max()),
                'skewness': float(stats.skew(column_data)),
                'kurtosis': float(stats.kurtosis(column_data))
            }

            # Distribution characteristics
            stats_info['is_normal'] = abs(stats_info['skewness']) < 0.5 and abs(stats_info['kurtosis']) < 3
            stats_info['is_skewed'] = abs(stats_info['skewness']) > 1
            stats_info['variance_coefficient'] = stats_info['std'] / abs(stats_info['mean']) if stats_info['mean'] != 0 else 0

            distribution_info[column] = stats_info

        return distribution_info

    def _analyze_correlations(self, data: pd.DataFrame) -> Dict[str, Any]:
        """Analyze correlations between variables."""
        correlation_info = {}

        numeric_data = data.select_dtypes(include=[np.number])

        if len(numeric_data.columns) > 1:
            correlation_matrix = numeric_data.corr()

            # Find highly correlated pairs
            high_correlations = []
            for i in range(len(correlation_matrix.columns)):
                for j in range(i + 1, len(correlation_matrix.columns)):
                    corr_value = correlation_matrix.iloc[i, j]
                    if abs(corr_value) > 0.7:  # High correlation threshold
                        high_correlations.append({
                            'feature1': correlation_matrix.columns[i],
                            'feature2': correlation_matrix.columns[j],
                            'correlation': float(corr_value)
                        })

            correlation_info = {
                'correlation_matrix': correlation_matrix.to_dict(),
                'high_correlations': high_correlations,
                'avg_absolute_correlation': correlation_matrix.abs().mean().mean()
            }

        return correlation_info

    def _analyze_target_column(self, data: pd.DataFrame, target_column: str) -> Dict[str, Any]:
        """Analyze target column specifically."""
        target_data = data[target_column].dropna()

        analysis = {
            'type': 'numeric' if data[target_column].dtype in ['int64', 'float64'] else 'categorical',
            'missing_percentage': (data[target_column].isnull().sum() / len(data)) * 100
        }

        if analysis['type'] == 'numeric':
            analysis.update({
                'mean': float(target_data.mean()),
                'std': float(target_data.std()),
                'min': float(target_data.min()),
                'max': float(target_data.max()),
                'distribution_skew': float(stats.skew(target_data))
            })
        else:
            analysis.update({
                'unique_values': int(target_data.nunique()),
                'value_counts': target_data.value_counts().head(10).to_dict(),
                'is_balanced': (target_data.value_counts().max() / len(target_data)) < 0.8
            })

        return analysis

    def _handle_missing_values(self, strategy: str = 'auto'):
        """Handle missing values based on strategy."""
        original_missing = self.cleaned_data.isnull().sum().sum()

        if strategy == 'auto':
            # Auto-select strategy based on data characteristics
            for column in self.cleaned_data.columns:
                missing_pct = (self.cleaned_data[column].isnull().sum() / len(self.cleaned_data)) * 100

                if missing_pct > 50:
                    # Drop column if more than 50% missing
                    self.cleaned_data.drop(column, axis=1, inplace=True)
                    self.cleaning_report['steps_performed'].append(f"Dropped column '{column}' (>{missing_pct:.1f}% missing)")

                elif missing_pct > 0:
                    if self.cleaned_data[column].dtype in ['int64', 'float64']:
                        # Numeric: use median for skewed data, mean for normal
                        if abs(stats.skew(self.cleaned_data[column].dropna())) > 1:
                            self.cleaned_data[column].fillna(self.cleaned_data[column].median(), inplace=True)
                        else:
                            self.cleaned_data[column].fillna(self.cleaned_data[column].mean(), inplace=True)
                    else:
                        # Categorical: use mode
                        mode_value = self.cleaned_data[column].mode()
                        if len(mode_value) > 0:
                            self.cleaned_data[column].fillna(mode_value[0], inplace=True)

        elif strategy == 'knn':
            # Use KNN imputation for numeric columns
            numeric_columns = self.cleaned_data.select_dtypes(include=[np.number]).columns
            if len(numeric_columns) > 0:
                imputer = KNNImputer(n_neighbors=5)
                self.cleaned_data[numeric_columns] = imputer.fit_transform(self.cleaned_data[numeric_columns])

        final_missing = self.cleaned_data.isnull().sum().sum()
        self.cleaning_report['changes_made']['missing_values_handled'] = original_missing - final_missing

    def _remove_duplicates(self):
        """Remove duplicate rows."""
        original_length = len(self.cleaned_data)
        self.cleaned_data.drop_duplicates(inplace=True)
        duplicates_removed = original_length - len(self.cleaned_data)

        if duplicates_removed > 0:
            self.cleaning_report['changes_made']['duplicates_removed'] = duplicates_removed
            self.cleaning_report['steps_performed'].append(f"Removed {duplicates_removed} duplicate rows")

    def _handle_outliers(self, strategy: str = 'iqr'):
        """Handle outliers based on strategy."""
        numeric_columns = self.cleaned_data.select_dtypes(include=[np.number]).columns
        outliers_handled = {}

        for column in numeric_columns:
            original_length = len(self.cleaned_data)

            if strategy == 'iqr':
                Q1 = self.cleaned_data[column].quantile(0.25)
                Q3 = self.cleaned_data[column].quantile(0.75)
                IQR = Q3 - Q1
                lower_bound = Q1 - 1.5 * IQR
                upper_bound = Q3 + 1.5 * IQR

                # Remove outliers
                self.cleaned_data = self.cleaned_data[
                    (self.cleaned_data[column] >= lower_bound) &
                    (self.cleaned_data[column] <= upper_bound)
                ]

            elif strategy == 'zscore':
                z_scores = np.abs(stats.zscore(self.cleaned_data[column].dropna()))
                self.cleaned_data = self.cleaned_data[
                    (self.cleaned_data[column].notna()) &
                    (z_scores <= 3)
                ]

            outliers_removed = original_length - len(self.cleaned_data)
            if outliers_removed > 0:
                outliers_handled[column] = outliers_removed

        if outliers_handled:
            self.cleaning_report['changes_made']['outliers_removed'] = outliers_handled
            self.cleaning_report['steps_performed'].append(f"Removed outliers from {len(outliers_handled)} columns")

    def _fix_data_types(self):
        """Fix and optimize data types."""
        type_conversions = {}

        for column in self.cleaned_data.columns:
            original_type = str(self.cleaned_data[column].dtype)

            # Try to convert to more efficient types
            if self.cleaned_data[column].dtype == 'object':
                # Try numeric conversion
                try:
                    self.cleaned_data[column] = pd.to_numeric(self.cleaned_data[column])
                    type_conversions[column] = f"{original_type} -> numeric"
                except:
                    # Try datetime conversion
                    try:
                        self.cleaned_data[column] = pd.to_datetime(self.cleaned_data[column])
                        type_conversions[column] = f"{original_type} -> datetime"
                    except:
                        pass

            # Optimize numeric types
            elif self.cleaned_data[column].dtype in ['int64', 'float64']:
                if self.cleaned_data[column].dtype == 'int64':
                    min_val = self.cleaned_data[column].min()
                    max_val = self.cleaned_data[column].max()

                    if min_val >= 0:  # Unsigned
                        if max_val < 255:
                            self.cleaned_data[column] = self.cleaned_data[column].astype('uint8')
                            type_conversions[column] = "int64 -> uint8"
                        elif max_val < 65535:
                            self.cleaned_data[column] = self.cleaned_data[column].astype('uint16')
                            type_conversions[column] = "int64 -> uint16"
                    else:  # Signed
                        if min_val >= -128 and max_val <= 127:
                            self.cleaned_data[column] = self.cleaned_data[column].astype('int8')
                            type_conversions[column] = "int64 -> int8"

        if type_conversions:
            self.cleaning_report['changes_made']['type_conversions'] = type_conversions
            self.cleaning_report['steps_performed'].append(f"Optimized {len(type_conversions)} column types")

    def _standardize_text_columns(self):
        """Standardize text data."""
        text_columns = self.cleaned_data.select_dtypes(include=['object']).columns
        standardized_columns = []

        for column in text_columns:
            # Skip if it's actually categorical with few unique values
            if self.cleaned_data[column].nunique() / len(self.cleaned_data) < 0.1:
                continue

            # Basic text cleaning
            self.cleaned_data[column] = self.cleaned_data[column].astype(str).str.strip()
            self.cleaned_data[column] = self.cleaned_data[column].str.lower()
            standardized_columns.append(column)

        if standardized_columns:
            self.cleaning_report['changes_made']['text_standardized'] = standardized_columns
            self.cleaning_report['steps_performed'].append(f"Standardized {len(standardized_columns)} text columns")

    def _generate_feature_suggestions(self, target_column: str = None):
        """Generate feature engineering suggestions."""
        suggestions = []

        # Interaction features for numeric columns
        numeric_columns = self.cleaned_data.select_dtypes(include=[np.number]).columns
        if len(numeric_columns) > 1:
            suggestions.append({
                'type': 'interaction_features',
                'description': 'Create interaction features between numeric columns',
                'example': f"Create {numeric_columns[0]} * {numeric_columns[1]} for potential non-linear relationships"
            })

        # Polynomial features
        if len(numeric_columns) > 0:
            suggestions.append({
                'type': 'polynomial_features',
                'description': 'Create polynomial features for non-linear relationships',
                'example': f"Add {numeric_columns[0]}² or {numeric_columns[0]}³ terms"
            })

        # Binning for continuous variables
        for column in numeric_columns:
            if self.cleaned_data[column].nunique() > 50:
                suggestions.append({
                    'type': 'binning',
                    'description': f'Create bins for {column}',
                    'example': f'Convert {column} to categorical using quartiles or custom bins'
                })

        # One-hot encoding for categorical variables
        categorical_columns = self.cleaned_data.select_dtypes(include=['object']).columns
        if len(categorical_columns) > 0:
            for column in categorical_columns:
                if self.cleaned_data[column].nunique() < 20:  # Reasonable cardinality
                    suggestions.append({
                        'type': 'one_hot_encoding',
                        'description': f'Apply one-hot encoding to {column}',
                        'example': f'Convert {column} to binary columns for each category'
                    })

        self.cleaning_report['recommendations'] = suggestions

    def _calculate_quality_score(self, analysis: Dict[str, Any]) -> float:
        """Calculate overall data quality score."""
        score = 100.0

        # Deduct for missing values
        missing_penalty = analysis['missing_values']['missing_percentage'] * 0.5
        score -= missing_penalty

        # Deduct for duplicates
        duplicate_penalty = analysis['duplicates']['duplicate_percentage'] * 0.3
        score -= duplicate_penalty

        # Deduct for outliers (weighted by severity)
        outlier_penalty = 0
        for column, outlier_data in analysis['outliers'].items():
            max_outlier_pct = max([outlier_data[method]['percentage'] for method in outlier_data.keys()])
            outlier_penalty += max_outlier_pct * 0.1
        score -= outlier_penalty

        # Deduct for data type issues
        type_issues = sum(1 for col, dtype in analysis['data_types'].items() if dtype == 'object')
        type_penalty = (type_issues / len(analysis['data_types'])) * 5
        score -= type_penalty

        return max(0, min(100, score))

    def _assess_cleaning_quality(self):
        """Assess the quality improvement after cleaning."""
        if self.original_data is not None and self.cleaned_data is not None:
            # Re-analyze cleaned data
            cleaned_analysis = self.analyze_dataset(self.cleaned_data)
            original_analysis = self.analyze_dataset(self.original_data)

            quality_improvement = {
                'original_quality_score': original_analysis.get('quality_score', 0),
                'cleaned_quality_score': cleaned_analysis.get('quality_score', 0),
                'improvement': cleaned_analysis.get('quality_score', 0) - original_analysis.get('quality_score', 0),
                'rows_removed': len(self.original_data) - len(self.cleaned_data),
                'columns_removed': len(self.original_data.columns) - len(self.cleaned_data.columns)
            }

            self.cleaning_report['quality_improvement'] = quality_improvement

def generate_cleaning_report(analysis: Dict[str, Any], cleaning_report: Dict[str, Any]) -> str:
    """Generate a human-readable cleaning report."""
    report = []
    report.append("# Data Cleaning Report\n")

    # Summary
    report.append("## Summary")
    report.append(f"- Original dataset: {cleaning_report['original_shape'][0]} rows, {cleaning_report['original_shape'][1]} columns")
    report.append(f"- Final dataset: {cleaning_report['final_shape'][0]} rows, {cleaning_report['final_shape'][1]} columns")

    if 'quality_improvement' in cleaning_report:
        improvement = cleaning_report['quality_improvement']
        report.append(f"- Quality score improved from {improvement['original_quality_score']:.1f} to {improvement['cleaned_quality_score']:.1f}")
        report.append(f"- Overall improvement: {improvement['improvement']:.1f} points")

    report.append("")

    # Steps performed
    if cleaning_report['steps_performed']:
        report.append("## Cleaning Steps Performed")
        for step in cleaning_report['steps_performed']:
            report.append(f"- {step}")
        report.append("")

    # Changes made
    if cleaning_report['changes_made']:
        report.append("## Changes Made")
        for change_type, change_data in cleaning_report['changes_made'].items():
            report.append(f"### {change_type.replace('_', ' ').title()}")
            if isinstance(change_data, dict):
                for key, value in change_data.items():
                    report.append(f"- {key}: {value}")
            else:
                report.append(f"- {change_data}")
            report.append("")

    # Recommendations
    if cleaning_report.get('recommendations'):
        report.append("## Feature Engineering Recommendations")
        for i, rec in enumerate(cleaning_report['recommendations'], 1):
            report.append(f"{i}. **{rec['type'].replace('_', ' ').title()}**")
            report.append(f"   - {rec['description']}")
            report.append(f"   - Example: {rec['example']}")
            report.append("")

    return "\n".join(report)