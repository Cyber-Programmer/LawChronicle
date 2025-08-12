# AI-Powered Statute Date Extractor

A comprehensive tool that combines Excel processing, AI-powered date extraction, and GUI-based review for automatically filling missing dates in statute databases.

## 🚀 Features

- **Excel Processing**: Efficient NumPy-based processing of Excel files to identify statutes with missing dates
- **AI Integration**: GPT-4 powered intelligent date extraction from statute sections
- **Interactive GUI**: User-friendly interface for reviewing and approving extracted dates
- **Batch Processing**: Process multiple statutes with progress tracking
- **Confidence Scoring**: AI provides confidence scores and reasoning for each extraction
- **Database Integration**: Direct MongoDB integration for saving approved dates
- **Configurable**: JSON-based configuration for easy customization

## 📋 Prerequisites

- Python 3.8+
- MongoDB instance running locally or remotely
- Azure OpenAI API key and endpoint
- Excel files with statute data

## 🛠️ Installation

1. **Install Dependencies**:
   ```bash
   pip install -r requirements_ai_extractor.txt
   ```

2. **Set Azure OpenAI Environment Variables**:
   ```bash
   # Windows
   set AZURE_OPENAI_API_KEY=your-azure-api-key-here
   set AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com/
   set AZURE_OPENAI_API_VERSION=2024-02-15-preview
   set AZURE_OPENAI_DEPLOYMENT_NAME=gpt-4
   
   # Linux/Mac
   export AZURE_OPENAI_API_KEY=your-azure-api-key-here
   export AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com/
   export AZURE_OPENAI_API_VERSION=2024-02-15-preview
   export AZURE_OPENAI_DEPLOYMENT_NAME=gpt-4
   ```

3. **Configure Database**:
   - Ensure MongoDB is running
   - Update `config_ai_extractor.json` with your database settings

## 📊 Excel File Format

Your Excel file should have the following structure:

| Statute Name | Province | Date | Statute Type | ... |
|--------------|----------|------|--------------|-----|
| Statute A    | Ontario  |      | Act          | ... |
| Statute B    | Quebec   | 2020-01-01 | Regulation | ... |

**Column Configuration** (modify in `config_ai_extractor.json`):
- Column 0: Statute Name
- Column 1: Province  
- Column 2: Date (target field for filling)
- Column 3: Statute Type

## 🎯 Usage

### 1. Basic Usage

```bash
python ai_date_extractor.py
```

### 2. Workflow

1. **Load Excel Data**:
   - Click "Browse" to select your Excel file
   - Click "Load Excel Data" to identify statutes with missing dates

2. **AI Processing**:
   - Click "Process with AI" to extract dates from statute sections
   - Monitor progress in the status bar
   - AI will analyze statute sections and provide dates with confidence scores

3. **Review & Approve**:
   - Select statutes from the list to view details
   - Review AI-extracted dates, confidence scores, and reasoning
   - Click "Approve Date" or "Reject" for each statute
   - View statute sections to verify AI reasoning

4. **Save to Database**:
   - Click "Save Approved Dates" to update your MongoDB database
   - Only approved dates will be saved

### 3. Configuration

Edit `config_ai_extractor.json` to customize:

```json
{
    "excel_config": {
        "date_column_index": 2,        // Excel column for dates
        "statute_name_column": 0,      // Excel column for statute names
        "province_column": 1,          // Excel column for provinces
        "statute_type_column": 3       // Excel column for statute types
    },
         "ai_config": {
         "model": "gpt-4",              // AI model to use
         "temperature": 0.1,            // AI creativity (0-1)
         "confidence_threshold": 70,    // Minimum confidence for auto-approval
         "azure_deployment_name": "gpt-4",  // Azure deployment name
         "azure_api_version": "2024-02-15-preview"  // Azure API version
     }
}
```

## 🔧 Advanced Features

### Batch Processing
The tool processes statutes in batches to optimize API usage and provide progress feedback.

### Confidence Scoring
AI provides confidence scores (0-100) for each date extraction:
- **90-100**: High confidence, likely accurate
- **70-89**: Good confidence, review recommended
- **50-69**: Moderate confidence, careful review needed
- **<50**: Low confidence, manual verification required

### Error Handling
- Graceful handling of API errors and rate limits
- Automatic retry logic for failed requests
- Detailed error logging and user feedback

### Performance Optimization
- NumPy arrays for efficient Excel data processing
- Background threading for non-blocking AI processing
- Configurable batch sizes and API delays

## 📁 File Structure

```
04_date_processing/
├── ai_date_extractor.py          # Main application
├── config_ai_extractor.json      # Configuration file
├── requirements_ai_extractor.txt  # Python dependencies
├── README_AI_Date_Extractor.md   # This file
└── missing_dates_gui_tkinter.py  # Original GUI (for reference)
```

## 🐛 Troubleshooting

### Common Issues

1. **API Key Error**:
   - Ensure Azure OpenAI environment variables are set
   - Verify API key, endpoint, and deployment name are correct
   - Check if deployment has sufficient quota

2. **MongoDB Connection Error**:
   - Check if MongoDB is running
   - Verify connection string in configuration
   - Ensure database and collection exist

3. **Excel Loading Error**:
   - Verify Excel file format and column structure
   - Check file permissions
   - Ensure file is not corrupted

4. **AI Processing Errors**:
   - Check internet connection
   - Verify API rate limits
   - Review error logs for specific issues

### Debug Mode

Enable debug logging by modifying the script:
```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

## 📈 Performance Tips

1. **Optimize Excel Files**:
   - Remove unnecessary columns
   - Clean data before processing
   - Use consistent formatting

2. **API Usage**:
   - Process in smaller batches for large datasets
   - Monitor Azure OpenAI usage and quota
   - Use appropriate deployment (GPT-4 for accuracy, GPT-3.5 for speed)

3. **Database Performance**:
   - Ensure proper indexing on statute names
   - Use connection pooling for large operations
   - Monitor database performance

## 🔒 Security Considerations

- Store Azure OpenAI credentials securely (use environment variables)
- Validate all user inputs
- Implement proper error handling
- Consider data privacy requirements
- Use secure database connections

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🆘 Support

For issues and questions:
1. Check the troubleshooting section
2. Review error logs
3. Create an issue with detailed information
4. Include configuration and sample data (if possible)

---

**Note**: This tool uses AI for date extraction. Always review and verify extracted dates before saving to your database. The AI provides confidence scores to help with decision-making, but human oversight is recommended for critical legal documents. 