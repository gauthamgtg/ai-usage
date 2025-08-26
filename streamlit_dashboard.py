import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import json
import boto3
import psycopg2
from functools import wraps
import logging
import traceback
import sys
from streamlit_option_menu import option_menu

# Page configuration
st.set_page_config(
    page_title="AI Usage Dashboard",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Multi-page navigation
selected_page = option_menu(
    menu_title=None,
    options=["Dashboard", "Raw Data"],
    icons=["📊", "📋"],
    menu_icon="cast",
    default_index=0,
    orientation="horizontal",
    styles={
        "container": {"padding": "0!important", "background-color": "#fafafa"},
        "icon": {"color": "orange", "font-size": "18px"},
        "nav-link": {
            "font-size": "16px",
            "text-align": "left",
            "margin": "0px",
            "--hover-color": "#eee",
        },
        "nav-link-selected": {"background-color": "#02ab21"},
    }
)

# Custom CSS removed - using native Streamlit components

# Configure logging with custom handler to capture logs
class StreamlitLogHandler(logging.Handler):
    def __init__(self):
        super().__init__()
        self.log_records = []
    
    def emit(self, record):
        self.log_records.append(record)
        # Keep only last 100 records
        if len(self.log_records) > 100:
            self.log_records.pop(0)
    
    def get_logs(self):
        return self.log_records

# Configure logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

# Create custom handler
streamlit_handler = StreamlitLogHandler()
streamlit_handler.setLevel(logging.DEBUG)

# Create formatter
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
streamlit_handler.setFormatter(formatter)

# Add handler to logger
logger.addHandler(streamlit_handler)

# Also add console handler for development
console_handler = logging.StreamHandler(sys.stdout)
console_handler.setLevel(logging.DEBUG)
console_handler.setFormatter(formatter)
logger.addHandler(console_handler)

# Initialize session state
if 'data_loaded' not in st.session_state:
    st.session_state.data_loaded = False

# AWS Secrets Manager client setup
client = boto3.client(
    "secretsmanager",
    region_name=st.secrets["AWS_DEFAULT_REGION"],
    aws_access_key_id=st.secrets["AWS_ACCESS_KEY_ID"],
    aws_secret_access_key=st.secrets["AWS_SECRET_ACCESS_KEY"]
)

def get_secret(secret_name):
    """Retrieve the secret value from AWS Secrets Manager"""
    try:
        response = client.get_secret_value(SecretId=secret_name)
        return json.loads(response["SecretString"])
    except Exception as e:
        st.error(f"Error retrieving secret {secret_name}: {e}")
        return None

# Get database credentials from AWS Secrets Manager
secret = get_secret("G-streamlit-KAT")
if secret:
    db = secret["db"]
    name = secret["name"]
    passw = secret["passw"]
    server = secret["server"]
    port = secret["port"]
    stripe_key = secret["stripe"]
    st.success("✅ Successfully connected to AWS Secrets Manager!")
else:
    st.error("❌ Failed to retrieve database credentials from AWS Secrets Manager")
    # Fallback to environment variables or manual configuration
    db = st.secrets.get("DB_NAME", "your_database_name")
    name = st.secrets.get("DB_USER", "your_username")
    passw = st.secrets.get("DB_PASSWORD", "your_password")
    server = st.secrets.get("DB_HOST", "your_host")
    port = st.secrets.get("DB_PORT", "your_port")

# Database connection decorator (same as your st.py)
def redshift_connection(dbname, user, password, host, port):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            try:
                connection = psycopg2.connect(
                    dbname=dbname,
                    user=user,
                    password=password,
                    host=host,
                    port=port
                )
                cursor = connection.cursor()
                print("Connected to Redshift!")
                
                result = func(*args, connection=connection, cursor=cursor, **kwargs)
                
                cursor.close()
                connection.close()
                print("Disconnected from Redshift!")
                
                return result
            except Exception as e:
                print(f"Error: {e}")
                st.error(f"Database connection error: {e}")
                return None
        return wrapper
    return decorator

class AIUsageProcessor:
    def __init__(self):
        logger.info("Initializing AIUsageProcessor")
        self.ai_usage_data = None
        self.optimization_data = None
        self.user_subscriptions_data = None
        self.agent_chats_data = None
        self.creatives_library_data = None
        logger.info("AIUsageProcessor initialized successfully")
        
    def _process_timestamp_columns(self, df, timestamp_columns):
        """Helper method to convert timestamp columns to datetime"""
        for col in timestamp_columns:
            if col in df.columns:
                df[col] = pd.to_datetime(df[col], errors='coerce')
        return df
    
    def _process_json_columns(self, df, json_columns):
        """Helper method to parse JSON columns"""
        for col in json_columns:
            if col in df.columns:
                df[f'{col}_parsed'] = df[col].apply(
                    lambda x: json.loads(x) if x and x != 'null' else {}
                )
        return df
    
    def _process_numeric_columns(self, df, numeric_columns, fill_value=0):
        """Helper method to convert columns to numeric with fill value"""
        for col in numeric_columns:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce').fillna(fill_value)
        return df
    

    
    def _validate_dataframe(self, df, method_name):
        """Helper method to validate dataframe for common operations"""
        logger.debug(f"Validating dataframe in {method_name}")
        logger.debug(f"Dataframe type: {type(df)}")
        logger.debug(f"Dataframe is None: {df is None}")
        
        if df is None:
            logger.warning(f"Dataframe is None in {method_name}")
            st.warning(f"Warning: {method_name} called with None dataframe")
            return False
        
        if not isinstance(df, pd.DataFrame):
            logger.error(f"Dataframe is not a pandas DataFrame in {method_name}. Type: {type(df)}")
            st.error(f"Error: {method_name} received invalid dataframe type: {type(df)}")
            return False
        
        logger.debug(f"Dataframe shape: {df.shape}")
        logger.debug(f"Dataframe columns: {df.columns.tolist() if hasattr(df, 'columns') else 'No columns'}")
        logger.debug(f"Dataframe is empty: {df.empty}")
        
        if df.empty:
            logger.warning(f"Dataframe is empty in {method_name}")
            st.warning(f"Warning: {method_name} called with empty dataframe")
            return False
        
        logger.debug(f"Dataframe validation passed for {method_name}")
        return True
    

    
    def _prepare_dataframe_for_display(self, df):
        """Prepare dataframe for Streamlit display by converting problematic data types"""
        if df is None or df.empty:
            return df
        
        try:
            # Create a copy to avoid modifying original data
            display_df = df.copy()
            
            # Convert problematic data types
            for col in display_df.columns:
                # Handle numpy int64/float64 types that cause PyArrow issues
                if display_df[col].dtype == 'int64':
                    display_df[col] = display_df[col].astype('int32')
                elif display_df[col].dtype == 'float64':
                    display_df[col] = display_df[col].astype('float32')
                elif display_df[col].dtype == 'object':
                    # Convert object columns to string to avoid PyArrow issues
                    display_df[col] = display_df[col].astype('string')
            
            return display_df
        except Exception as e:
            logger.warning(f"Error preparing dataframe for display: {e}")
            return df
    
    def _execute_database_query(self, query, timestamp_columns=None, json_columns=None):
        """Generic method to execute database queries with common processing"""
        logger.info(f"Executing database query: {query[:100]}...")
        
        try:
            # Use the actual database connection with decorator pattern
            @redshift_connection(db, name, passw, server, port)
            def execute_query(connection, cursor):
                cursor.execute(query)
                column_names = [desc[0] for desc in cursor.description]
                result = pd.DataFrame(cursor.fetchall(), columns=column_names)
                
                # Process timestamp columns if specified
                if timestamp_columns:
                    result = self._process_timestamp_columns(result, timestamp_columns)
                
                # Process JSON columns if specified
                if json_columns:
                    result = self._process_json_columns(result, json_columns)
                    
                return result
            
            result = execute_query()
            
            if result is not None:
                logger.info(f"Query executed successfully, returned {len(result)} records")
                return result
            else:
                logger.warning("Query returned None, returning empty dataframe")
                return pd.DataFrame()
                
        except Exception as e:
            logger.error(f"Error executing database query: {e}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            st.error(f"Database query error: {e}")
            return pd.DataFrame()
    
    def fetch_optimization_data(self):
        """Fetch optimization suggestions data from database"""
        logger.info("Fetching optimization data from database")
        
        query = """
        SELECT id,
            ad_account_id,
            campaign_id,
            adset_id,
            ad_id,
            optimization_type,
            level,
            meta_data,
            status,
            is_success,
            error_message,
            applied_by,
            applied_at,
            created_at,
            updated_at
        FROM zocket_global.optimization_suggestions
        ORDER BY created_at DESC
        """
        
        result = self._execute_database_query(
            query=query,
            timestamp_columns=['applied_at', 'created_at', 'updated_at'],
            json_columns=['meta_data']
        )
        
        logger.info(f"Optimization data fetched: {len(result)} records")
        return result
    
    def fetch_agent_chats_data(self):
        """Fetch agent chats data from database"""
        logger.info("Fetching agent chats data from database")
        
        query = """
        SELECT 
            id,
            title,
            -- messages,
            business_id,
            agent_name,
            -- choices,
            stream_id,
            created_at,
            updated_at
        FROM zocket_global.agent_chats
        ORDER BY created_at DESC
        """
        
        result = self._execute_database_query(
            query=query,
            timestamp_columns=['created_at', 'updated_at'],
            json_columns=['messages', 'choices']
        )
        
        logger.info(f"Agent chats data fetched: {len(result)} records")
        return result
    
    def fetch_creatives_library_data(self):
        """Fetch creatives library data filtered by chat_id from database"""
        logger.info("Fetching creatives library data from database")
        
        query = """
         SELECT 
            a.*,buid
        FROM zocket_global.creatives_library a 
        left join 
                (SELECT
                id as bpid ,brand_name,json_extract_path_text(json_extract_array_element_text(business_user_ids, 0), 'role') AS role,
                json_extract_path_text(json_extract_array_element_text(business_user_ids, 0), 'business_user_id') AS buid
            FROM
                zocket_global.business_profile
            WHERE
                json_extract_path_text(json_extract_array_element_text(business_user_ids, 0), 'role') = 'owner' )bp on a.business_id=bp.bpid
        WHERE chat_id IS NOT NULL
        ORDER BY created_at DESC
        """
        
        result = self._execute_database_query(
            query=query,
            timestamp_columns=['created_at', 'updated_at']
        )
        
        logger.info(f"Creatives library data fetched: {len(result)} records")
        return result
    
    def fetch_user_subscriptions_data(self):
        """Fetch user subscriptions data with prompt credits from database"""
        logger.info("Fetching user subscriptions data from database")
        
        query = """
        SELECT 
            business_user_id,
            start_date,
            end_date,
            prompt_credits,
            created_at,
            updated_at
        FROM zocket_global.user_subscriptions
        where end_date >= current_date and prompt_credits<100
        ORDER BY created_at DESC
        """
        
        result = self._execute_database_query(
            query=query,
            timestamp_columns=['start_date', 'end_date', 'created_at', 'updated_at']
        )
        
        # Convert prompt_credits to numeric
        if not result.empty and 'prompt_credits' in result.columns:
            result = self._process_numeric_columns(result, ['prompt_credits'], fill_value=100)
        
        logger.info(f"User subscriptions data fetched: {len(result)} records")
        return result
    
    def calculate_ai_usage_metrics(self):
        """Calculate AI usage metrics from existing optimization data"""
        logger.info("Calculating AI usage metrics from optimization data")
        
        if self.optimization_data is None or self.optimization_data.empty:
            logger.warning("No optimization data available for calculating AI usage metrics")
            return pd.DataFrame()
        
        try:
            # Calculate overall metrics (no date grouping)
            total_suggestions = len(self.optimization_data)
            published_suggestions = len(self.optimization_data[self.optimization_data['status'] == 'PUBLISHED'])
            successful_optimizations = len(self.optimization_data[self.optimization_data['is_success'] == 1])
            failed_optimizations = len(self.optimization_data[self.optimization_data['is_success'] == 0])
            
            # Create a simple summary dataframe
            summary_data = pd.DataFrame({
                'metric': ['total_suggestions', 'published_suggestions', 'successful_optimizations', 'failed_optimizations'],
                'value': [total_suggestions, published_suggestions, successful_optimizations, failed_optimizations]
            })
            
            logger.info(f"AI usage metrics calculated: {len(summary_data)} summary records")
            return summary_data
            
        except Exception as e:
            logger.error(f"Error calculating AI usage metrics: {e}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            return pd.DataFrame()
    
    def load_data(self):
        """Load and process AI usage data from database"""
        logger.info("Starting to load data from database")
        
        try:
            # Fetch all data from database
            logger.info("Fetching optimization data...")
            self.optimization_data = self.fetch_optimization_data()
            
            logger.info("Calculating AI usage metrics...")
            self.ai_usage_data = self.calculate_ai_usage_metrics()
            
            logger.info("Fetching user subscriptions...")
            self.user_subscriptions_data = self.fetch_user_subscriptions_data()
            
            logger.info("Fetching agent chats...")
            self.agent_chats_data = self.fetch_agent_chats_data()
            
            logger.info("Fetching creatives library...")
            self.creatives_library_data = self.fetch_creatives_library_data()
            
            # Log summary of loaded data
            logger.info("Data loading completed successfully")
            logger.info(f"Optimization data: {len(self.optimization_data)} records")
            logger.info(f"AI usage data: {len(self.ai_usage_data)} records")
            logger.info(f"User subscriptions: {len(self.user_subscriptions_data)} records")
            logger.info(f"Agent chats: {len(self.agent_chats_data)} records")
            logger.info(f"Creatives library: {len(self.creatives_library_data)} records")
            
            return True
            
        except Exception as e:
            logger.error(f"Error loading AI usage data: {e}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            return False
    
    def get_summary_metrics(self):
        """Calculate summary metrics for the AI Usage dashboard"""
        logger.info("Getting summary metrics")
        logger.debug(f"Optimization data type: {type(self.optimization_data)}")
        logger.debug(f"Optimization data is None: {self.optimization_data is None}")
        
        if self.optimization_data is None:
            logger.warning("Optimization data is None, returning empty metrics")
            return {}
        
        if not isinstance(self.optimization_data, pd.DataFrame):
            logger.error(f"Optimization data is not a DataFrame: {type(self.optimization_data)}")
            return {}
        
        if self.optimization_data.empty:
            logger.warning("Optimization data is empty, returning empty metrics")
            return {}
        
        try:
            logger.debug(f"Optimization data shape: {self.optimization_data.shape}")
            logger.debug(f"Optimization data columns: {self.optimization_data.columns.tolist()}")
            
            # Calculate current metrics
            total_suggestions = self.optimization_data.shape[0]
            logger.debug(f"Total suggestions: {total_suggestions}")
            
            # Check if required columns exist
            required_columns = ['status', 'is_success']
            missing_columns = [col for col in required_columns if col not in self.optimization_data.columns]
            if missing_columns:
                logger.error(f"Missing required columns: {missing_columns}")
                logger.debug(f"Available columns: {self.optimization_data.columns.tolist()}")
                return {}
            
            total_published = self.optimization_data[self.optimization_data['status'] == 'PUBLISHED'].shape[0]
            total_successful = self.optimization_data[self.optimization_data['is_success'] == 1].shape[0]
            total_failed = self.optimization_data[self.optimization_data['is_success'] == 0].shape[0]
            
            logger.debug(f"Total published: {total_published}")
            logger.debug(f"Total successful: {total_successful}")
            logger.debug(f"Total failed: {total_failed}")
            
            # Calculate success rate
            success_rate = (total_successful / total_suggestions * 100) if total_suggestions > 0 else 0
            adoption_rate = (total_published / total_suggestions * 100) if total_suggestions > 0 else 0
            
            logger.debug(f"Success rate: {success_rate}%")
            logger.debug(f"Adoption rate: {adoption_rate}%")
            
            # Calculate daily metrics
            daily_suggestions = 0
            daily_published = 0
            daily_successful = 0
            
            if self.ai_usage_data is not None and isinstance(self.ai_usage_data, pd.DataFrame) and not self.ai_usage_data.empty:
                logger.debug("AI usage data available, calculating daily metrics")
                try:
                    if 'total_suggestions' in self.ai_usage_data.columns:
                        daily_suggestions = self.ai_usage_data['total_suggestions'].iloc[-1]
                    if 'published_suggestions' in self.ai_usage_data.columns:
                        daily_published = self.ai_usage_data['published_suggestions'].iloc[-1]
                    if 'successful_optimizations' in self.ai_usage_data.columns:
                        daily_successful = self.ai_usage_data['successful_optimizations'].iloc[-1]
                except Exception as e:
                    logger.error(f"Error calculating daily metrics: {e}")
                    logger.debug(f"AI usage data columns: {self.ai_usage_data.columns.tolist()}")
            else:
                logger.debug("AI usage data not available, using default values")
            
            # Calculate growth (simplified for demo)
            suggestions_growth = 15.2
            published_growth = 8.7
            successful_growth = 12.4
            
            metrics = {
                'total_suggestions': total_suggestions,
                'total_published': total_published,
                'total_successful': total_successful,
                'total_failed': total_failed,
                'success_rate': round(success_rate, 2),
                'adoption_rate': round(adoption_rate, 2),
                'daily_suggestions': daily_suggestions,
                'daily_published': daily_published,
                'daily_successful': daily_successful,
                'suggestions_growth': suggestions_growth,
                'published_growth': published_growth,
                'successful_growth': successful_growth
            }
            
            logger.info(f"Summary metrics calculated successfully: {len(metrics)} metrics")
            logger.debug(f"Metrics: {metrics}")
            return metrics
            
        except Exception as e:
            logger.error(f"Error calculating summary metrics: {e}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            st.error(f"Error calculating summary metrics: {e}")
            return {}
    
    def get_prompt_credits_metrics(self):
        """Calculate prompt credits utilization metrics"""
        logger.info("Getting prompt credits metrics")
        
        if not self._validate_dataframe(self.user_subscriptions_data, 'get_prompt_credits_metrics'):
            return {}
        
        try:
            # Filter active subscriptions
            active_subscriptions = self.user_subscriptions_data.copy()
            logger.debug(f"Active subscriptions shape: {active_subscriptions.shape}")
            
            # Check required columns
            required_columns = ['prompt_credits', 'created_at']
            missing_columns = [col for col in required_columns if col not in active_subscriptions.columns]
            if missing_columns:
                logger.error(f"Missing required columns for credits metrics: {missing_columns}")
                logger.debug(f"Available columns: {active_subscriptions.columns.tolist()}")
                return {}
            
            # Calculate metrics
            total_users = len(active_subscriptions)
            logger.debug(f"Total users: {total_users}")
            
            total_credits_allocated = active_subscriptions['prompt_credits'].sum()
            logger.debug(f"Total credits allocated: {total_credits_allocated}")
            
            avg_credits_per_user = total_credits_allocated / total_users if total_users > 0 else 0
            logger.debug(f"Average credits per user: {avg_credits_per_user}")
            
            # Calculate credit utilization (assuming default is 100)
            default_credits = 100
            total_credits_consumed = (default_credits * total_users) - total_credits_allocated
            utilization_rate = (total_credits_consumed / (default_credits * total_users) * 100) if total_users > 0 else 0
            
            logger.debug(f"Total credits consumed: {total_credits_consumed}")
            logger.debug(f"Utilization rate: {utilization_rate}%")
            
            # All users (no date restriction)
            recent_users = total_users
            logger.debug(f"All users: {recent_users}")
            
            metrics = {
                'total_users': total_users,
                'total_credits_allocated': total_credits_allocated,
                'avg_credits_per_user': round(avg_credits_per_user, 2),
                'total_credits_consumed': total_credits_consumed,
                'utilization_rate': round(utilization_rate, 2),
                'recent_users': recent_users,
                'default_credits': default_credits
            }
            
            logger.info(f"Prompt credits metrics calculated successfully: {len(metrics)} metrics")
            logger.debug(f"Credits metrics: {metrics}")
            return metrics
            
        except Exception as e:
            logger.error(f"Error calculating prompt credits metrics: {e}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            st.error(f"Error calculating prompt credits metrics: {e}")
            return {}
    
    def get_agent_chats_metrics(self):
        """Calculate agent chats metrics and credit consumption"""
        if not self._validate_dataframe(self.agent_chats_data, 'get_agent_chats_metrics'):
            return {}
        
        # Basic metrics (all data, no date restriction)
        total_chats = len(self.agent_chats_data)
        total_businesses = self.agent_chats_data['business_id'].nunique()
        
        # All activity (no date restriction)
        recent_chats_count = total_chats
        recent_businesses = total_businesses
        
        # Agent usage analysis
        agent_usage = self.agent_chats_data['agent_name'].value_counts().reset_index()
        agent_usage.columns = ['agent_name', 'chat_count']
        top_agent = agent_usage.iloc[0] if not agent_usage.empty else {'agent_name': 'None', 'chat_count': 0}
        
        # Daily trends (simplified since we're not using date restrictions)
        avg_daily_chats = 0  # Not calculating daily trends for now
        
        return {
            'total_chats': total_chats,
            'total_businesses': total_businesses,
            'recent_chats_count': recent_chats_count,
            'recent_businesses': recent_businesses,
            'top_agent': top_agent['agent_name'],
            'top_agent_chats': top_agent['chat_count'],
            'avg_daily_chats': round(avg_daily_chats, 2)
        }
    
    def get_creatives_metrics(self):
        """Calculate creatives library metrics"""
        if not self._validate_dataframe(self.creatives_library_data, 'get_creatives_metrics'):
            return {}
        
        # Basic metrics
        total_creatives = len(self.creatives_library_data)
        total_businesses = self.creatives_library_data['business_id'].nunique()
        total_chats_with_creatives = self.creatives_library_data['chat_id'].nunique()
        
        # Creative type analysis
        creative_types = self.creatives_library_data['creative_type'].value_counts().reset_index()
        creative_types.columns = ['creative_type', 'count']
        top_creative_type = creative_types.iloc[0] if not creative_types.empty else {'creative_type': 'Unknown', 'count': 0}
        
        # All activity (no date restriction)
        recent_creatives_count = total_creatives
        
        # Conversion rate (chats that resulted in creatives)
        if self.agent_chats_data is not None and not self.agent_chats_data.empty:
            total_chats = len(self.agent_chats_data)
            conversion_rate = (total_chats_with_creatives / total_chats * 100) if total_chats > 0 else 0
        else:
            conversion_rate = 0
        
        return {
            'total_creatives': total_creatives,
            'total_businesses': total_businesses,
            'total_chats_with_creatives': total_chats_with_creatives,
            'recent_creatives_count': recent_creatives_count,
            'top_creative_type': top_creative_type['creative_type'],
            'top_creative_count': top_creative_type['count'],
            'conversion_rate': round(conversion_rate, 2),
            'creative_types': creative_types.to_dict('records') if not creative_types.empty else []
        }
    
    

    

    

    

    

    

    


# Initialize the AI usage processor
@st.cache_resource
def get_ai_processor():
    return AIUsageProcessor()

# Database connection is now configured using AWS Secrets Manager
# The same pattern as your st.py file is implemented

# Main dashboard
def main():

    # Sidebar
    with st.sidebar:
        st.header("Dashboard Controls")
        
        if st.button("🔄 Refresh Data", use_container_width=True):
            st.session_state.data_loaded = False
            st.rerun()
        
        if st.button("📊 Export Data", use_container_width=True):
            st.info("Export functionality would be implemented here")
        
        st.divider()
        
        st.header("Data Status")
        if st.session_state.data_loaded:
            st.success("✅ Data Loaded")
        else:
            st.warning("⏳ Loading Data...")
        

    
    # Initialize processor
    processor = get_ai_processor()
    
    # Load data
    if not st.session_state.data_loaded:
        with st.spinner("Loading AI usage data..."):
            logger.info("Starting data loading process")
            
            try:
                # Try to load data from database
                logger.info("Attempting to load data from database...")
                
                # Check if we have database connection configured
                # For now, we'll use the placeholder implementation
                success = processor.load_data()
                
                if success and any([
                    not processor.optimization_data.empty,
                    not processor.ai_usage_data.empty,
                    not processor.user_subscriptions_data.empty,
                    not processor.agent_chats_data.empty,
                    not processor.creatives_library_data.empty
                ]):
                    st.success("✅ Data loaded successfully from database!")
                    logger.info("Data loaded successfully from database")
                else:
                    st.warning("⚠️ No data available from database. Using empty dataframes.")
                    st.info("💡 To connect to your database, update the database credentials and connection logic in the AIUsageProcessor class.")
                    
                    # Initialize empty dataframes as fallback
                    logger.info("Initializing empty dataframes as fallback")
                    processor.optimization_data = pd.DataFrame()
                    processor.ai_usage_data = pd.DataFrame()
                    processor.user_subscriptions_data = pd.DataFrame()
                    processor.agent_chats_data = pd.DataFrame()
                    processor.creatives_library_data = pd.DataFrame()
                
                logger.info("Data loading process completed")
                logger.debug(f"Optimization data type: {type(processor.optimization_data)}")
                logger.debug(f"AI usage data type: {type(processor.ai_usage_data)}")
                logger.debug(f"User subscriptions data type: {type(processor.user_subscriptions_data)}")
                logger.debug(f"Agent chats data type: {type(processor.agent_chats_data)}")
                logger.debug(f"Creatives library data type: {type(processor.creatives_library_data)}")
                
                st.session_state.data_loaded = True
                logger.info("Data loading completed successfully")
                st.rerun()
                
            except Exception as e:
                logger.error(f"Error during data loading: {e}")
                logger.error(f"Traceback: {traceback.format_exc()}")
                st.error(f"Error loading data: {e}")
                st.session_state.data_loaded = False
    
    # Page navigation
    if selected_page == "Dashboard":
        # Display metrics
        display_metrics(processor)
        

        
        # Display tables
        display_tables(processor)
    
    elif selected_page == "Raw Data":
        # Display raw data page
        display_raw_data_page(processor)

def display_metrics(processor):
    """Display optimization summary metrics"""
    logger.info("Displaying optimization summary metrics")
    st.header("🔄 Optimization Summary Metrics")
    
    try:
        metrics = processor.get_summary_metrics()
        logger.debug(f"Retrieved metrics: {metrics}")
        
        if not metrics:
            logger.warning("No metrics available, displaying empty state")
            st.info("No metrics available. Please load data to see metrics.")
            return
        
        # Create metric columns for optimization summary
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            total_suggestions = metrics.get('total_suggestions', 0)
            logger.debug(f"Displaying total suggestions: {total_suggestions}")
            st.metric(
                label="Total Suggestions",
                value=f"{total_suggestions:,}"
            )
        
        with col2:
            total_published = metrics.get('total_published', 0)
            logger.debug(f"Displaying total published: {total_published}")
            st.metric(
                label="Published",
                value=f"{total_published:,}"
            )
        
        with col3:
            total_successful = metrics.get('total_successful', 0)
            logger.debug(f"Displaying total successful: {total_successful}")
            st.metric(
                label="Successful",
                value=f"{total_successful:,}"
            )
        
        with col4:
            total_failed = metrics.get('total_failed', 0)
            logger.debug(f"Displaying total failed: {total_failed}")
            st.metric(
                label="Failed",
                value=f"{total_failed:,}"
            )
        
        logger.info("Optimization summary metrics displayed successfully")
        
        # Show status distribution
        if processor.optimization_data is not None and not processor.optimization_data.empty:
            st.subheader("📊 Status Distribution")
            
            # Get status counts
            status_counts = processor.optimization_data['status'].value_counts()
            
            # Display status counts in columns
            status_cols = st.columns(len(status_counts))
            for i, (status, count) in enumerate(status_counts.items()):
                with status_cols[i]:
                    st.metric(
                        label=f"Status: {status}",
                        value=f"{count:,}"
                    )
            
            # Show optimization type distribution
            st.subheader("🎯 Optimization Type Distribution")
            
            # Get optimization type counts
            type_counts = processor.optimization_data['optimization_type'].value_counts()
            
            # Display type counts in columns (max 4 per row)
            max_cols_per_row = 4
            for i in range(0, len(type_counts), max_cols_per_row):
                row_types = type_counts.iloc[i:i+max_cols_per_row]
                type_cols = st.columns(len(row_types))
                for j, (opt_type, count) in enumerate(row_types.items()):
                    with type_cols[j]:
                        st.metric(
                            label=f"Type: {opt_type}",
                            value=f"{count:,}"
                        )
        
    except Exception as e:
        logger.error(f"Error displaying optimization summary metrics: {e}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        st.error(f"Error displaying metrics: {e}")
        st.info("Please check the logs for more details.")
    
    # Prompt Credits Metrics
    st.header("🪙 Prompt Credits Analysis")
    
    credits_metrics = processor.get_prompt_credits_metrics()
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric(
            label="Total Active Users",
            value=f"{credits_metrics.get('total_users', 0):,}",
            delta="Active Subscriptions"
        )
    
    with col2:
        st.metric(
            label="Credits Utilization",
            value=f"{credits_metrics.get('utilization_rate', 0)}%",
            delta="% of Credits Used"
        )
    
    with col3:
        st.metric(
            label="Avg Credits Remaining",
            value=f"{credits_metrics.get('avg_credits_per_user', 0):.1f}",
            delta="Per User"
        )
    
    with col4:
        st.metric(
            label="Total Users",
            value=f"{credits_metrics.get('recent_users', 0):,}",
            delta="All Time"
        )
    
    # Agent Chats Metrics
    st.header("💬 Agent Chats Analysis")
    
    agent_metrics = processor.get_agent_chats_metrics()
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric(
            label="Total Chats",
            value=f"{agent_metrics.get('total_chats', 0):,}",
            delta="All Time"
        )
    
    with col2:
        st.metric(
            label="Unique Businesses",
            value=f"{agent_metrics.get('total_businesses', 0):,}",
            delta="Using Agents"
        )
    
    with col3:
        st.metric(
            label="Total Chats",
            value=f"{agent_metrics.get('recent_chats_count', 0):,}",
            delta="All Time"
        )
    
    with col4:
        st.metric(
            label="Top Agent",
            value=agent_metrics.get('top_agent', 'N/A'),
            delta="Most Used"
        )
    
    # Creatives Metrics
    st.header("🎨 Creatives Generation Analysis")
    
    creatives_metrics = processor.get_creatives_metrics()
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric(
            label="Total Creatives",
            value=f"{creatives_metrics.get('total_creatives', 0):,}",
            delta="Generated"
        )
    
    with col2:
        st.metric(
            label="Chat to Creative",
            value=f"{creatives_metrics.get('conversion_rate', 0)}%",
            delta="Conversion Rate"
        )
    
    with col3:
        st.metric(
            label="Top Creative Type",
            value=creatives_metrics.get('top_creative_type', 'N/A'),
            delta="Most Generated"
        )
    
    with col4:
        st.metric(
            label="Total Creatives",
            value=f"{creatives_metrics.get('recent_creatives_count', 0):,}",
            delta="All Time"
        )


    

    

    

    


def display_tables(processor):
    """Display data tables"""
    st.header("📋 Detailed Data Tables")
    
    # Optimization Suggestions Table
    st.subheader("🔄 Recent Optimization Suggestions")
    
    if processor.optimization_data is not None and not processor.optimization_data.empty:
        # Show first 100 records for performance
        display_data = processor.optimization_data
        
        # Format the data for display
        display_data['created_at'] = display_data['created_at'].dt.strftime('%Y-%m-%d %H:%M')
        display_data['applied_at'] = display_data['applied_at'].dt.strftime('%Y-%m-%d %H:%M') if 'applied_at' in display_data.columns else None
        
        # Create a more readable table
        st.dataframe(
            display_data[['id', 'optimization_type', 'level', 'status', 'is_success', 'created_at']],
            use_container_width=True,
            hide_index=True
        )
        
        st.info(f"Showing all {len(processor.optimization_data)} records.")
    else:
        st.info("No optimization data available")
    
    # Agent Chats Table
    st.subheader("💬 Agent Chats & Generated Creatives")
    
    if processor.agent_chats_data is not None and not processor.agent_chats_data.empty:
        # Show first 100 records for performance
        display_data = processor.agent_chats_data
        
        # Format the data for display
        display_data['created_at'] = display_data['created_at'].dt.strftime('%Y-%m-%d %H:%M')
        
        # Create a more readable table
        st.dataframe(
            display_data[['id', 'business_id', 'agent_name', 'title', 'created_at']],
            use_container_width=True,
            hide_index=True
        )
        
        st.info(f"Showing all {len(processor.agent_chats_data)} records.")
    else:
        st.info("No agent chats data available")
    
    # User Subscriptions Table
    st.subheader("👤 User Subscriptions & Prompt Credits")
    
    if processor.user_subscriptions_data is not None and not processor.user_subscriptions_data.empty:
        # Show first 100 records for performance
        display_data = processor.user_subscriptions_data
        
        # Format datetime columns for display
        datetime_columns = ['start_date', 'end_date', 'created_at', 'updated_at']
        for col in datetime_columns:
            if col in display_data.columns:
                display_data[col] = display_data[col].dt.strftime('%Y-%m-%d %H:%M')
        
        # Create a more readable table with key columns
        key_columns = ['business_user_id', 'prompt_credits', 'start_date', 'end_date', 'created_at']
        available_columns = [col for col in key_columns if col in display_data.columns]
        
        st.dataframe(
            display_data[available_columns],
            use_container_width=True,
            hide_index=True
        )
        
        st.info(f"Showing all {len(processor.user_subscriptions_data)} records.")
        
        # Show summary statistics
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Total Subscriptions", len(processor.user_subscriptions_data))
        with col2:
            avg_credits = processor.user_subscriptions_data['prompt_credits'].mean() if 'prompt_credits' in processor.user_subscriptions_data.columns else 0
            st.metric("Avg Credits Remaining", f"{avg_credits:.1f}")
        with col3:
            low_credits = len(processor.user_subscriptions_data[processor.user_subscriptions_data['prompt_credits'] < 50]) if 'prompt_credits' in processor.user_subscriptions_data.columns else 0
            st.metric("Low Credits (<50)", low_credits)
    else:
        st.info("No user subscriptions data available")
    
    # Creatives Library Table
    st.subheader("🎨 Creatives Library & Business Profiles")
    
    if processor.creatives_library_data is not None and not processor.creatives_library_data.empty:
        # Show first 100 records for performance
        display_data = processor.creatives_library_data
        
        # Format datetime columns for display
        datetime_columns = ['created_at', 'updated_at']
        for col in datetime_columns:
            if col in display_data.columns:
                display_data[col] = display_data[col].dt.strftime('%Y-%m-%d %H:%M')
        
        # Create a more readable table with key columns
        key_columns = ['id', 'chat_id', 'business_id', 'creative_type', 'created_at']
        if 'buid' in display_data.columns:
            key_columns.append('buid')
        if 'url' in display_data.columns:
            key_columns.append('url')
        available_columns = [col for col in key_columns if col in display_data.columns]
        
        st.dataframe(
            display_data[available_columns],
            use_container_width=True,
            hide_index=True
        )
        
        st.info(f"Showing all {len(processor.creatives_library_data)} records with URL column.")
        
        # Show summary statistics
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Total Creatives", len(processor.creatives_library_data))
        with col2:
            unique_chats = processor.creatives_library_data['chat_id'].nunique() if 'chat_id' in processor.creatives_library_data.columns else 0
            st.metric("Unique Chats", unique_chats)
        with col3:
            unique_businesses = processor.creatives_library_data['business_id'].nunique() if 'business_id' in processor.creatives_library_data.columns else 0
            st.metric("Unique Businesses", unique_businesses)
    else:
        st.info("No creatives library data available")

def display_raw_data_page(processor):
    """Display raw data page with all tables and data"""
    st.header("📋 Raw Data Tables")
    st.markdown("This page displays all raw data from the database tables.")
    
    # Data loading status
    if not st.session_state.get('data_loaded', False):
        st.warning("⚠️ Data not loaded yet. Please go to the Dashboard page and click 'Refresh Data' first.")
        return
    
    # Optimization Suggestions Raw Data
    st.subheader("🔄 Optimization Suggestions - Raw Data")
    if processor.optimization_data is not None and not processor.optimization_data.empty:
        st.write(f"**Total Records:** {len(processor.optimization_data)}")
        st.write(f"**Columns:** {list(processor.optimization_data.columns)}")
        
        # Data info
        col1, col2 = st.columns(2)
        with col1:
            st.write("**Data Types:**")
            st.write(processor.optimization_data.dtypes)
        with col2:
            st.write("**Missing Values:**")
            st.write(processor.optimization_data.isnull().sum())
        
        # Raw data table with pagination
        st.subheader("📊 Raw Data Table")
        page_size = st.selectbox("Records per page:", [50, 100, 200, 500], key="opt_page_size")
        
        total_pages = (len(processor.optimization_data) + page_size - 1) // page_size
        current_page = st.number_input("Page:", min_value=1, max_value=total_pages, value=1, key="opt_page")
        
        start_idx = (current_page - 1) * page_size
        end_idx = start_idx + page_size
        
        page_data = processor.optimization_data.iloc[start_idx:end_idx].copy()
        
        # Format datetime columns for display
        datetime_columns = ['created_at', 'updated_at', 'applied_at']
        for col in datetime_columns:
            if col in page_data.columns:
                page_data[col] = page_data[col].dt.strftime('%Y-%m-%d %H:%M:%S')
        
        # Prepare dataframe for display to avoid PyArrow issues
        display_data = processor._prepare_dataframe_for_display(page_data)
        st.dataframe(display_data, use_container_width=True, hide_index=True)
        
        # Pagination info
        st.info(f"Showing records {start_idx + 1} to {min(end_idx, len(processor.optimization_data))} of {len(processor.optimization_data)} total records.")
        
        # Download button
        csv = processor.optimization_data.to_csv(index=False)
        st.download_button(
            label="📥 Download Optimization Data (CSV)",
            data=csv,
            file_name=f"optimization_suggestions_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
            mime="text/csv"
        )
    else:
        st.info("No optimization data available")
    
    st.markdown("---")
    
    # Agent Chats Raw Data
    st.subheader("💬 Agent Chats - Raw Data")
    if processor.agent_chats_data is not None and not processor.agent_chats_data.empty:
        st.write(f"**Total Records:** {len(processor.agent_chats_data)}")
        st.write(f"**Columns:** {list(processor.agent_chats_data.columns)}")
        
        # Data info
        col1, col2 = st.columns(2)
        with col1:
            st.write("**Data Types:**")
            st.write(processor.agent_chats_data.dtypes)
        with col2:
            st.write("**Missing Values:**")
            st.write(processor.agent_chats_data.isnull().sum())
        
        # Raw data table with pagination
        st.subheader("📊 Raw Data Table")
        page_size = st.selectbox("Records per page:", [50, 100, 200, 500], key="chat_page_size")
        
        total_pages = (len(processor.agent_chats_data) + page_size - 1) // page_size
        current_page = st.number_input("Page:", min_value=1, max_value=total_pages, value=1, key="chat_page")
        
        start_idx = (current_page - 1) * page_size
        end_idx = start_idx + page_size
        
        page_data = processor.agent_chats_data.iloc[start_idx:end_idx].copy()
        
        # Format datetime columns for display
        datetime_columns = ['created_at', 'updated_at']
        for col in datetime_columns:
            if col in page_data.columns:
                page_data[col] = page_data[col].dt.strftime('%Y-%m-%d %H:%M:%S')
        
        # Prepare dataframe for display to avoid PyArrow issues
        display_data = processor._prepare_dataframe_for_display(page_data)
        st.dataframe(display_data, use_container_width=True, hide_index=True)
        
        # Pagination info
        st.info(f"Showing records {start_idx + 1} to {min(end_idx, len(processor.agent_chats_data))} of {len(processor.agent_chats_data)} total records.")
        
        # Download button
        csv = processor.agent_chats_data.to_csv(index=False)
        st.download_button(
            label="📥 Download Agent Chats Data (CSV)",
            data=csv,
            file_name=f"agent_chats_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
            mime="text/csv"
        )
    else:
        st.info("No agent chats data available")
    
    st.markdown("---")
    
    # Creatives Library Raw Data
    st.subheader("🎨 Creatives Library - Raw Data")
    if processor.creatives_library_data is not None and not processor.creatives_library_data.empty:
        st.write(f"**Total Records:** {len(processor.creatives_library_data)}")
        st.write(f"**Columns:** {list(processor.creatives_library_data.columns)}")
        
        # Data info
        col1, col2 = st.columns(2)
        with col1:
            st.write("**Data Types:**")
            st.write(processor.creatives_library_data.dtypes)
        with col2:
            st.write("**Missing Values:**")
            st.write(processor.creatives_library_data.isnull().sum())
        
        # Raw data table with pagination
        st.subheader("📊 Raw Data Table")
        page_size = st.selectbox("Records per page:", [50, 100, 200, 500], key="creatives_page_size")
        
        total_pages = (len(processor.creatives_library_data) + page_size - 1) // page_size
        current_page = st.number_input("Page:", min_value=1, max_value=total_pages, value=1, key="creatives_page")
        
        start_idx = (current_page - 1) * page_size
        end_idx = start_idx + page_size
        
        page_data = processor.creatives_library_data.iloc[start_idx:end_idx].copy()
        
        # Format datetime columns for display
        datetime_columns = ['created_at', 'updated_at']
        for col in datetime_columns:
            if col in page_data.columns:
                page_data[col] = page_data[col].dt.strftime('%Y-%m-%d %H:%M:%S')
        
        # Prepare dataframe for display to avoid PyArrow issues
        display_data = processor._prepare_dataframe_for_display(page_data)
        st.dataframe(display_data, use_container_width=True, hide_index=True)
        
        # Pagination info
        st.info(f"Showing records {start_idx + 1} to {min(end_idx, len(processor.creatives_library_data))} of {len(processor.creatives_library_data)} total records.")
        
        # Download button
        csv = processor.creatives_library_data.to_csv(index=False)
        st.download_button(
            label="📥 Download Creatives Data (CSV)",
            data=csv,
            file_name=f"creatives_library_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
            mime="text/csv"
        )
    else:
        st.info("No creatives library data available")
    
    st.markdown("---")
    
    # User Subscriptions Raw Data
    st.subheader("👤 User Subscriptions - Raw Data")
    if processor.user_subscriptions_data is not None and not processor.user_subscriptions_data.empty:
        st.write(f"**Total Records:** {len(processor.user_subscriptions_data)}")
        st.write(f"**Columns:** {list(processor.user_subscriptions_data.columns)}")
        
        # Data info
        col1, col2 = st.columns(2)
        with col1:
            st.write("**Data Types:**")
            st.write(processor.user_subscriptions_data.dtypes)
        with col2:
            st.write("**Missing Values:**")
            st.write(processor.user_subscriptions_data.isnull().sum())
        
        # Raw data table with pagination
        st.subheader("📊 Raw Data Table")
        page_size = st.selectbox("Records per page:", [50, 100, 200, 500], key="subs_page_size")
        
        total_pages = (len(processor.user_subscriptions_data) + page_size - 1) // page_size
        current_page = st.number_input("Page:", min_value=1, max_value=total_pages, value=1, key="subs_page")
        
        start_idx = (current_page - 1) * page_size
        end_idx = start_idx + page_size
        
        page_data = processor.user_subscriptions_data.iloc[start_idx:end_idx].copy()
        
        # Format datetime columns for display
        datetime_columns = ['start_date', 'end_date', 'created_at', 'updated_at']
        for col in datetime_columns:
            if col in page_data.columns:
                page_data[col] = page_data[col].dt.strftime('%Y-%m-%d %H:%M:%S')
        
        # Prepare dataframe for display to avoid PyArrow issues
        display_data = processor._prepare_dataframe_for_display(page_data)
        st.dataframe(display_data, use_container_width=True, hide_index=True)
        
        # Pagination info
        st.info(f"Showing records {start_idx + 1} to {min(end_idx, len(processor.user_subscriptions_data))} of {len(processor.user_subscriptions_data)} total records.")
        
        # Download button
        csv = processor.user_subscriptions_data.to_csv(index=False)
        st.download_button(
            label="📥 Download User Subscriptions Data (CSV)",
            data=csv,
            file_name=f"user_subscriptions_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
            mime="text/csv"
        )
    else:
        st.info("No user subscriptions data available")
    
    st.markdown("---")
    
    # AI Usage Metrics Raw Data
    st.subheader("🤖 AI Usage Metrics - Raw Data")
    if processor.ai_usage_data is not None and not processor.ai_usage_data.empty:
        st.write(f"**Total Records:** {len(processor.ai_usage_data)}")
        st.write(f"**Columns:** {list(processor.ai_usage_data.columns)}")
        
        # Data info
        col1, col2 = st.columns(2)
        with col1:
            st.write("**Data Types:**")
            st.write(processor.ai_usage_data.dtypes)
        with col2:
            st.write("**Missing Values:**")
            st.write(processor.ai_usage_data.isnull().sum())
        
        # Raw data table with pagination
        st.subheader("📊 Raw Data Table")
        page_size = st.selectbox("Records per page:", [50, 100, 200, 500], key="ai_page_size")
        
        total_pages = (len(processor.ai_usage_data) + page_size - 1) // page_size
        current_page = st.number_input("Page:", min_value=1, max_value=total_pages, value=1, key="ai_page")
        
        start_idx = (current_page - 1) * page_size
        end_idx = start_idx + page_size
        
        page_data = processor.ai_usage_data.iloc[start_idx:end_idx].copy()
        
        # Format datetime columns for display
        datetime_columns = ['created_at', 'updated_at']
        for col in datetime_columns:
            if col in page_data.columns:
                page_data[col] = page_data[col].dt.strftime('%Y-%m-%d %H:%M:%S')
        
        # Prepare dataframe for display to avoid PyArrow issues
        display_data = processor._prepare_dataframe_for_display(page_data)
        st.dataframe(display_data, use_container_width=True, hide_index=True)
        
        # Pagination info
        st.info(f"Showing records {start_idx + 1} to {min(end_idx, len(processor.ai_usage_data))} of {len(processor.ai_usage_data)} total records.")
        
        # Download button
        csv = processor.ai_usage_data.to_csv(index=False)
        st.download_button(
            label="📥 Download AI Usage Metrics Data (CSV)",
            data=csv,
            file_name=f"ai_usage_metrics_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
            mime="text/csv"
        )
    else:
        st.info("No AI usage metrics data available")

if __name__ == "__main__":
    main()
