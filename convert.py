import geopandas as gpd

regions = gpd.read_file("static/BR_Regioes_2022/BR_Regioes_2022.shp")
states = gpd.read_file("static/BR_UF_2022/BR_UF_2022.shp")

regions.to_file("static/regions.geojson", driver="GeoJSON")
states.to_file("static/states.geojson", driver="GeoJSON")