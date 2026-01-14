import kagglehub

# Download latest version
path = kagglehub.dataset_download("saitamachiha/chess-dataset-for-chess-engine")

print("Path to dataset files:", path)