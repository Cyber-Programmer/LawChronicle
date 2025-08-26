# 🧠 Intelligent Grouping GUI System

## Overview

The Intelligent Grouping GUI System provides context-aware, intelligent analysis for statute and section grouping in LawChronicle. This system goes beyond simple name matching to understand legal relationships, constitutional amendments, and legal lineage.

## 🚀 Key Features

### **Context-Aware Analysis**
- **Constitutional Amendment Detection**: Automatically identifies constitutional amendments and their relationships
- **Legal Lineage Analysis**: Understands how statutes relate to each other through amendments
- **Amendment Chain Building**: Creates chronological chains of constitutional amendments

### **Intelligent Grouping**
- **Context-Based Grouping**: Groups statutes based on legal relationships, not just names
- **Confidence Scoring**: Provides confidence levels for all grouping decisions
- **Manual Override**: Allows legal experts to validate and override automated decisions

### **Advanced GPT Integration**
- **Conditional Prompting**: Uses different prompts for different legal contexts
- **Legal Expert Personas**: Specialized prompts for Pakistani constitutional law
- **Fallback Mechanisms**: Rule-based alternatives when GPT analysis fails

## 🛠️ Available Tools

### 1. **Full Intelligent Grouping GUI** (`intelligent_grouping_gui.py`)
Complete context-aware analysis system with:
- Constitutional lineage detection
- Legal context analysis
- Relationship mapping
- Intelligent grouping decisions
- Comprehensive export options

### 2. **Constitutional Amendment Detector** (`constitutional_amendment_detector_gui.py`)
Focused tool specifically for:
- Constitutional amendment detection
- Amendment chain visualization
- Amendment relationship analysis
- Chain export and reporting

### 3. **Launcher** (`launch_intelligent_grouping.py`)
Simple launcher that allows you to choose between tools and manage configuration.

## 📋 Prerequisites

### **Required Python Packages**
```bash
pip install tkinter pymongo openai numpy rapidfuzz
```

### **Required Services**
- **MongoDB**: Running instance with your statute data
- **Azure OpenAI**: API key and endpoint for GPT-4 analysis

### **Data Structure**
Your MongoDB collections should contain statutes with these fields:
- `Statute_Name`: Name of the statute
- `Province`: Province/region
- `Preamble`: Preamble text
- `Sections`: Array of section data
- `Date`: Statute date
- `Statute_Type`: Type of statute

## ⚙️ Configuration

### **1. Edit Configuration File**
Open `config_intelligent_grouping.json` and update:

```json
{
  "mongo_uri": "mongodb://localhost:27017",
  "source_db": "Your-Source-Database",
  "source_collection": "Your-Source-Collection",
  
  "azure_openai": {
    "api_key": "your-azure-openai-api-key",
    "endpoint": "your-azure-openai-endpoint",
    "model": "gpt-4o",
    "temperature": 0.1,
    "max_tokens": 1000
  }
}
```

### **2. Database Connection**
Ensure your MongoDB instance is running and accessible with the configured URI.

### **3. Azure OpenAI Setup**
- Get your API key from Azure OpenAI service
- Configure the endpoint URL
- Ensure you have access to GPT-4o model

## 🚀 Quick Start

### **Option 1: Use the Launcher (Recommended)**
```bash
cd gui/
python launch_intelligent_grouping.py
```

### **Option 2: Run Individual Tools**
```bash
# Full intelligent grouping tool
python intelligent_grouping_gui.py

# Constitutional amendment detector only
python constitutional_amendment_detector_gui.py
```

## 📖 Usage Guide

### **Step 1: Load Statutes**
1. Launch the tool of your choice
2. Verify database connection settings
3. Click "Load Statutes" to load your data
4. Verify the number of statutes loaded

### **Step 2: Run Analysis**
1. **For Full Tool**: Click "Start Context Analysis" to analyze all statutes
2. **For Amendment Detector**: Click "Start Detection" to find constitutional amendments
3. Monitor progress in the status bar

### **Step 3: Review Results**
1. **Context Analysis Tab**: View individual statute analysis
2. **Relationships Tab**: See detected relationships between statutes
3. **Intelligent Grouping Tab**: Review created groups
4. **Statistics Tab**: View comprehensive analysis statistics

### **Step 4: Export Results**
1. **Export Groups**: Save intelligent grouping results
2. **Export Analysis**: Save context analysis data
3. **Export Report**: Generate comprehensive markdown report

## 🔍 Understanding the Analysis

### **Constitutional Amendment Detection**
The system analyzes each statute to determine if it's a constitutional amendment by:
- Examining the statute name for constitutional references
- Analyzing preamble text for amendment language
- Using GPT-4 to understand legal context
- Providing confidence scores for decisions

### **Legal Lineage Analysis**
Identifies relationships between statutes by:
- Finding legal references (Article X, Section Y)
- Detecting amendment targets
- Understanding relationship types (amendment, repeal, addition)
- Building legal lineage trees

### **Intelligent Grouping**
Creates groups based on:
- Constitutional amendment chains
- Legal lineage relationships
- Amendment relationships
- Confidence thresholds
- Manual expert validation

## 📊 Output Formats

### **JSON Export**
- **Groups**: Complete grouping information with metadata
- **Analysis**: Full context analysis results
- **Chains**: Amendment chain structures

### **Markdown Reports**
- **Executive Summary**: Key findings and statistics
- **Detailed Analysis**: Comprehensive breakdown of results
- **Amendment Chains**: Visual representation of constitutional amendments

## ⚠️ Important Notes

### **Performance Considerations**
- **Large Datasets**: Processing time scales with dataset size
- **API Limits**: Respect Azure OpenAI rate limits
- **Memory Usage**: Monitor memory consumption for large datasets

### **Accuracy and Validation**
- **Confidence Scores**: Use confidence thresholds to filter results
- **Expert Review**: Always validate critical grouping decisions
- **Fallback Logic**: System gracefully degrades when GPT analysis fails

### **Data Quality**
- **Text Quality**: Better results with clean, well-formatted text
- **Metadata**: Complete metadata improves analysis accuracy
- **Consistency**: Consistent data structure across statutes

## 🐛 Troubleshooting

### **Common Issues**

#### **1. MongoDB Connection Failed**
- Verify MongoDB is running
- Check connection URI
- Ensure network access

#### **2. Azure OpenAI Not Available**
- Verify API key and endpoint
- Check API quota and limits
- Ensure model access

#### **3. No Statutes Loaded**
- Check database and collection names
- Verify data exists in collection
- Check data structure

#### **4. Analysis Fails**
- Check internet connection
- Verify API credentials
- Review error logs

### **Debug Mode**
Enable detailed logging by modifying the configuration:
```json
{
  "logging": {
    "level": "DEBUG",
    "log_gpt_responses": true
  }
}
```

## 🔧 Customization

### **Prompt Templates**
Modify prompts in the configuration file:
```json
{
  "prompt_templates": {
    "constitutional_amendment": {
      "system": "Your custom system prompt",
      "user_template": "Your custom user template"
    }
  }
}
```

### **Confidence Thresholds**
Adjust sensitivity of grouping decisions:
```json
{
  "context_analysis": {
    "confidence_threshold": 0.8
  }
}
```

### **Processing Parameters**
Customize batch processing:
```json
{
  "processing": {
    "batch_size": 1000,
    "max_workers": 8
  }
}
```

## 📚 API Reference

### **Key Classes**

#### **IntelligentContextAnalyzer**
- `analyze_constitutional_lineage(statute)`: Analyze constitutional relationships
- `analyze_legal_context(statute)`: Analyze legal context and references
- `analyze_relationship(statute_a, statute_b)`: Analyze relationship between statutes

#### **ConstitutionalAmendmentDetector**
- `detect_constitutional_amendment(statute)`: Detect constitutional amendments
- `_get_fallback_analysis(statute)`: Fallback analysis when GPT fails

### **Data Structures**

#### **StatuteContext**
```python
@dataclass
class StatuteContext:
    statute_id: str
    statute_name: str
    constitutional_lineage: Dict
    legal_context: Dict
    amendment_targets: List[str]
    legal_references: List[str]
    confidence_score: float
    analysis_timestamp: datetime
```

#### **StatuteRelationship**
```python
@dataclass
class StatuteRelationship:
    statute_a_id: str
    statute_b_id: str
    relationship_type: str
    confidence_score: float
    context_analysis: Dict
    gpt_analysis: Dict
    manual_override: bool
    override_reason: str
```

## 🚀 Future Enhancements

### **Planned Features**
- **Section-Level Analysis**: Intelligent section grouping and versioning
- **Multi-Language Support**: Support for different legal systems
- **Advanced Visualization**: Interactive relationship graphs
- **Batch Processing**: Command-line interface for automation
- **API Integration**: REST API for external access

### **Contributing**
To contribute to the intelligent grouping system:
1. Fork the repository
2. Create feature branch
3. Implement changes
4. Add tests
5. Submit pull request

## 📞 Support

### **Documentation**
- **Technical Implementation**: See `INTELLIGENT_GROUPING_TECHNICAL_IMPLEMENTATION.md`
- **Feasibility Study**: See `INTELLIGENT_GROUPING_FEASIBILITY_STUDY.md`
- **Executive Summary**: See `INTELLIGENT_GROUPING_EXECUTIVE_SUMMARY.md`

### **Issues**
- Report bugs through GitHub issues
- Include error logs and configuration details
- Provide sample data for reproduction

### **Questions**
- Check existing documentation
- Review configuration examples
- Consult the troubleshooting section

---

**The Intelligent Grouping GUI System represents a significant advancement in legal document analysis, providing context-aware understanding that goes far beyond simple text matching. Use it to discover hidden relationships, preserve legal lineage, and create truly intelligent groupings of your legal documents.** 🚀
