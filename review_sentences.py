#!/usr/bin/env python3
"""
review_sentences.py

Purpose
-------
Review the sentences and triples before evaluation to ensure that all sentences are correctly processed.

This script will:
1. Parse the input CSV file.
2. Display the sentences and triples for review.
3. Allow you to verify that all sentences are correctly formatted before evaluation.
"""

import csv
import pandas as pd


def review_sentences(csv_file):
    """
    Review the sentences and triples in the CSV file.
    
    Parameters
    ----------
    csv_file : str
        Path to the CSV file containing the sentences and triples.
    """
    # Read the CSV file
    df = pd.read_csv(csv_file)
    
    # Display the sentences and triples
    print("Review of Sentences and Triples:")
    print("=" * 80)
    for index, row in df.iterrows():
        print(f"Sentence {index + 1}:")
        print(f"  Subject: {row['subject']}")
        print(f"  Predicate: {row['predicate']}")
        print(f"  Object: {row['object']}")
        print(f"  Sentence: {row['sentence']}")
        print("-" * 80)
    
    # Display summary
    print(f"\nTotal Sentences: {len(df)}")
    print(f"Total Triples: {len(df)}")
    print("\nReview complete. All sentences and triples are displayed above.")


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser()
    parser.add_argument("--csv_file", required=True, help="Path to the CSV file containing the sentences and triples.")
    args = parser.parse_args()
    
    review_sentences(args.csv_file)