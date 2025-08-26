# AI Usage Dashboard - Streamlit Version

A comprehensive Streamlit dashboard that monitors AI optimization performance, provides intelligent recommendations, and tracks various AI usage metrics.

## Features

### 📊 **Summary Metrics**
- Total AI optimization suggestions
- Success and adoption rates
- Daily performance indicators
- Growth tracking with percentage changes

### 🪙 **Prompt Credits Analysis**
- Total active users and subscriptions
- Credit utilization rates
- Average credits remaining per user
- Recent user activity tracking

### 💬 **Agent Chats Analysis**
- Total chat interactions
- Unique business usage
- Recent activity monitoring
- Top-performing agents

### 🎨 **Creatives Generation Analysis**
- Total creative assets generated
- Chat-to-creative conversion rates
- Creative type distribution
- Recent generation activity

### 🤖 **AI Recommendations**
- Intelligent performance insights
- Priority-based recommendations
- Actionable optimization suggestions
- Performance trend analysis

### 📈 **Interactive Charts**
- Optimization trends over time
- Status distribution analysis
- Type performance comparisons
- Level-based performance metrics
- Credit consumption patterns
- Agent chat trends
- Creative type analysis

### 📋 **Detailed Data Tables**
- Recent optimization suggestions
- Agent chats and generated creatives
- Paginated data display
- Export functionality

## Installation

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd ai-usage
   ```

2. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Run the dashboard**
   ```bash
   streamlit run streamlit_dashboard.py
   ```

## Usage

### 🚀 **Getting Started**
1. Launch the dashboard using `streamlit run streamlit_dashboard.py`
2. The dashboard will open in your default web browser
3. **Navigate Pages**: Use the horizontal menu to switch between "Dashboard" and "Raw Data"
4. Use the sidebar controls to manage data and settings

### 🧪 **Test Data Mode**
- Click "🧪 Test Data Loading" to load minimal test data for debugging
- Helps verify dashboard functionality without full database connection
- Useful for testing and development purposes

### 🔄 **Data Management**
- **Refresh Data**: Reload all data and recalculate metrics
- **Export Data**: Download dashboard data in CSV format
- **Data Status**: Monitor data loading status in the sidebar

### 📱 **Responsive Design**
- Optimized for desktop and tablet viewing
- Wide layout for better chart visibility
- Responsive grid system for all screen sizes

## Configuration

### 🔌 **Database Connection**
The dashboard now uses the exact same database connection pattern as your existing code:

1. **AWS Secrets Manager**: Automatically retrieves database credentials from `G-streamlit-KAT` secret
2. **Redshift Connection**: Uses the same `redshift_connection` decorator pattern
3. **Secure Credentials**: No hardcoded credentials in the code
4. **Fallback Support**: Environment variables as backup if AWS Secrets Manager fails

#### **Required Configuration:**
Create a `.streamlit/secrets.toml` file with your AWS credentials:
```toml
AWS_DEFAULT_REGION = "ap-south-1"
AWS_ACCESS_KEY_ID = "your_aws_access_key_id"
AWS_SECRET_ACCESS_KEY = "your_aws_secret_access_key"
```

#### **Database Tables Used:**
- `zocket_global.optimization_suggestions`
- `zocket_global.agent_chats`
- `zocket_global.creatives_library`
- `zocket_global.user_subscriptions`
- `zocket_global.business_profile`

### 🎨 **Customization**
- **Colors**: Modify CSS variables in the custom styling section
- **Charts**: Customize Plotly chart configurations
- **Metrics**: Add or remove metric calculations
- **Tables**: Adjust table columns and pagination
- **Debug Logging**: Comprehensive logging for troubleshooting

## Data Sources

The dashboard integrates with the following data sources:

- **Optimization Suggestions**: AI-generated optimization recommendations
- **User Subscriptions**: User credit and subscription management
- **Agent Chats**: AI agent interaction logs
- **Creatives Library**: Generated creative assets
- **AI Usage Metrics**: Performance and usage statistics

## 📋 **Raw Data Page**

The dashboard now includes a dedicated **Raw Data** page that provides comprehensive access to all database tables:

### **Features:**
- **📊 Complete Data View**: All columns and records from each table
- **📄 Pagination**: Navigate through large datasets (50, 100, 200, 500 records per page)
- **📥 Data Export**: Download each table as CSV with timestamped filenames
- **🔍 Data Analysis**: View data types, missing values, and record counts
- **📱 Responsive Tables**: Optimized for both desktop and mobile viewing

### **Available Tables:**
1. **🔄 Optimization Suggestions**: AI optimization recommendations and status
2. **💬 Agent Chats**: AI agent interaction logs and conversations
3. **🎨 Creatives Library**: Generated creative assets and metadata
4. **👤 User Subscriptions**: User credit management and subscription data
5. **🤖 AI Usage Metrics**: Performance statistics and usage patterns

### **How to Use:**
1. **Navigate**: Use the horizontal navigation menu to switch between "Dashboard" and "Raw Data"
2. **Load Data**: Ensure data is loaded from the Dashboard page first
3. **Browse**: Use pagination controls to navigate through large datasets
4. **Export**: Download any table as CSV for external analysis
5. **Analyze**: Review data types, missing values, and record counts

## Architecture

### 🏗️ **Class Structure**
- **`AIUsageProcessor`**: Main data processing and analysis engine
- **`redshift_connection`**: Database connection decorator
- **Display Functions**: Modular UI components for different sections

### 📊 **Data Flow**
1. **Data Loading**: Fetch data from database or generate demo data
2. **Processing**: Calculate metrics, generate charts, and analyze trends
3. **Display**: Render interactive components and visualizations
4. **User Interaction**: Handle user controls and data updates

### 🔄 **State Management**
- **Session State**: Manages data loading and demo mode
- **Caching**: Optimizes performance with Streamlit caching
- **Real-time Updates**: Refreshes data based on user actions

## Performance Features

### ⚡ **Optimization**
- **Data Caching**: Reduces redundant calculations
- **Lazy Loading**: Loads data only when needed
- **Pagination**: Handles large datasets efficiently
- **Chart Optimization**: Responsive chart rendering

### 📱 **User Experience**
- **Loading States**: Clear feedback during data processing
- **Error Handling**: Graceful fallbacks for missing data
- **Responsive Design**: Works on all device sizes
- **Interactive Elements**: Hover effects and click interactions

## Troubleshooting

### 🚨 **Common Issues**

1. **Database Connection Errors**
   - Verify database credentials
   - Check network connectivity
   - Ensure required permissions

2. **Chart Display Issues**
   - Update Plotly to latest version
   - Check browser compatibility
   - Verify data format

3. **Performance Issues**
   - Reduce dataset size for testing
   - Enable caching for repeated operations
   - Monitor memory usage

### 🔧 **Debug Mode**
- **Built-in Debug Panel**: Use the "🐛 Show Debug Info" checkbox in the sidebar
- **Real-time Logs**: View detailed logging information directly in the dashboard
- **Dataframe Status**: Monitor the state of all data sources
- **Error Tracking**: Comprehensive error logging with full stack traces
- **Console Logs**: Monitor terminal output for additional debugging information

## Contributing

### 📝 **Development Setup**
1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test thoroughly
5. Submit a pull request

### 🧪 **Testing**
- Test with different data sizes
- Verify chart responsiveness
- Check mobile compatibility
- Validate export functionality

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Support

For support and questions:
- Create an issue in the repository
- Check the documentation
- Review the code comments
- Contact the development team

---

**Built with ❤️ using Streamlit, Plotly, and Pandas**
