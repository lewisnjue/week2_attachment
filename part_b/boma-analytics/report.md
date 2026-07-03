
# Part B: Data Acquisition Report

For this task, we decided to acquire data through **web scraping**. We collected property listing data from three popular real estate websites in Kenya:

* BuyRentKenya
* PropertyPro Kenya
* Property24 Kenya

After scraping the data, it was stored in a **NoSQL database (MongoDB)**. We used **MongoDB Atlas**, a cloud-based Database-as-a-Service (DBaaS) platform, to store the raw data collected from the three websites.

Once all the raw data had been collected, we performed a data transformation process to prepare the dataset for analysis. During this process, we discovered that the data obtained from **PropertyPro Kenya** was highly inconsistent compared to the other sources. Many records contained missing or incorrectly formatted information, making the dataset unreliable. As a result, we decided to exclude the PropertyPro data from the final dataset.

The remaining data from **BuyRentKenya** and **Property24 Kenya** was cleaned and transformed into a **CSV** file, which is easier to analyze using data analysis and machine learning tools.

The transformation pipeline produced the following summary:

## Export Summary

```text
Connecting to database to fetch data from 'unified_listings'...
Retrieved 32218 records. Converting to DataFrame...

--- Export Summary ---
File saved successfully to:
/home/njue/.projects/week_2_attachment/part_b/boma-analytics/data/boma_listings_modeling.csv

Total Rows: 32218
Total Columns/Features: 9
Feature Matrix Shape: (32218, 9)

Columns exported:
 - price_ksh          | Missing: 67    (0.2%)
 - source             | Missing: 0     (0.0%)
 - bathrooms          | Missing: 18823 (58.4%)
 - bedrooms           | Missing: 9664  (30.0%)
 - county             | Missing: 0     (0.0%)
 - floor_size_sqm     | Missing: 27749 (86.1%)
 - location           | Missing: 0     (0.0%)
 - parking            | Missing: 25397 (78.8%)
 - property_type      | Missing: 0     (0.0%)
```

From the export summary, it is evident that several features contain missing values. For example, the **floor_size_sqm**, **parking**, and **bathrooms** columns have a significant amount of missing data. If this dataset were to be used for machine learning, additional **data preprocessing** would be required to handle these missing values through techniques such as imputation or by removing incomplete records.

During data cleaning, we also identified several inconsistent records. For example, some properties had a listed price of **KSh 0**, which is clearly invalid and likely resulted from errors during data entry or scraping. Such records should be removed or corrected before performing any statistical analysis or training machine learning models.

After cleaning and excluding the inconsistent PropertyPro data, the final dataset contained **32,218 property listings** with **9 features**.

A sample of the transformed dataset is shown below:

```python
In [4]: df.head()

Out[4]:
    price_ksh        source  bathrooms  bedrooms         county  floor_size_sqm     location  parking property_type
0  53000000.0  buyrentkenya        NaN       5.0  Kiambu County             NaN  Kikuyu Town      NaN         House
1  26000000.0  buyrentkenya        NaN       4.0        Nairobi             NaN   Kileleshwa      NaN     Apartment
2  11000000.0  buyrentkenya        NaN       3.0  Kiambu County             NaN        Ruiru      NaN         House
3  17000000.0  buyrentkenya        NaN       3.0        Mombasa             NaN   Nyali Area      NaN     Apartment
4  54000000.0  buyrentkenya        NaN       4.0  Kilifi County             NaN         Bofa      NaN         House
```

The final dataset is suitable for exploratory data analysis and can also be used for predictive modeling after performing additional preprocessing, such as handling missing values, removing invalid records, and engineering relevant features.
