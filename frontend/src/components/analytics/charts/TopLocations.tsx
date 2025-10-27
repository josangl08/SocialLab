import React from 'react';
import './TopLocations.css';

interface LocationData {
  country_code?: string;
  city_name?: string;
  audience_count: number;
  percentage: number;
}

interface TopLocationsProps {
  countries: LocationData[];
  cities: LocationData[];
  loading?: boolean;
}

export const TopLocations: React.FC<TopLocationsProps> = ({
  countries,
  cities,
  loading = false
}) => {
  if (loading) {
    return (
      <div className="chart-loading">
        <div className="spinner"></div>
        <p>Cargando datos de ubicaciones...</p>
      </div>
    );
  }

  const hasCountries = countries && countries.length > 0;
  const hasCities = cities && cities.length > 0;

  if (!hasCountries && !hasCities) {
    return (
      <div className="chart-empty">
        <i className="bi bi-geo-alt" style={{ fontSize: '48px', color: '#d1d5db' }}></i>
        <p>No hay datos de ubicaciones disponibles</p>
      </div>
    );
  }

  // Mapeo de códigos de país a emojis de banderas
  const getCountryFlag = (countryCode: string) => {
    const codePoints = countryCode
      .toUpperCase()
      .split('')
      .map(char => 127397 + char.charCodeAt(0));
    return String.fromCodePoint(...codePoints);
  };

  const formatNumber = (num: number) => {
    if (num >= 1000000) return (num / 1000000).toFixed(1) + 'M';
    if (num >= 1000) return (num / 1000).toFixed(1) + 'K';
    return num.toString();
  };

  return (
    <div className="top-locations">
      {/* Countries Section */}
      {hasCountries && (
        <div className="locations-section">
          <h4 className="locations-title">
            <i className="bi bi-flag"></i>
            Top Países
          </h4>
          <div className="locations-list">
            {countries.slice(0, 5).map((country, index) => (
              <div key={country.country_code} className="location-item">
                <div className="location-rank">{index + 1}</div>
                <div className="location-flag">
                  {getCountryFlag(country.country_code || 'XX')}
                </div>
                <div className="location-info">
                  <div className="location-header">
                    <span className="location-name">{country.country_code}</span>
                    <span className="location-percentage">{country.percentage.toFixed(1)}%</span>
                  </div>
                  <div className="location-progress-bar">
                    <div
                      className="location-progress-fill"
                      style={{ width: `${country.percentage}%` }}
                    ></div>
                  </div>
                  <span className="location-count">
                    {formatNumber(country.audience_count)} seguidores
                  </span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Cities Section */}
      {hasCities && (
        <div className="locations-section">
          <h4 className="locations-title">
            <i className="bi bi-building"></i>
            Top Ciudades
          </h4>
          <div className="locations-list">
            {cities.slice(0, 5).map((city, index) => (
              <div key={city.city_name} className="location-item">
                <div className="location-rank">{index + 1}</div>
                <div className="location-icon">
                  <i className="bi bi-geo-alt-fill"></i>
                </div>
                <div className="location-info">
                  <div className="location-header">
                    <span className="location-name">{city.city_name}</span>
                    <span className="location-percentage">{city.percentage.toFixed(1)}%</span>
                  </div>
                  <div className="location-progress-bar">
                    <div
                      className="location-progress-fill city"
                      style={{ width: `${city.percentage}%` }}
                    ></div>
                  </div>
                  <span className="location-count">
                    {formatNumber(city.audience_count)} seguidores
                  </span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};

export default TopLocations;
