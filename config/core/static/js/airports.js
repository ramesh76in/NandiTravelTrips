"use strict";

/**
 * Nandi Travel Trips - Comprehensive Airport Database
 */
window.NandiAirports = [
    // Domestic Airports (India)
    {
        city: "Delhi",
        code: "DEL",
        airport: "Indira Gandhi International Airport",
        country: "India",
        category: "domestic"
    },
    {
        city: "Mumbai",
        code: "BOM",
        airport: "Chhatrapati Shivaji Maharaj International Airport",
        country: "India",
        category: "domestic"
    },
    {
        city: "Bengaluru",
        code: "BLR",
        airport: "Kempegowda International Airport",
        country: "India",
        category: "domestic"
    },
    {
        city: "Hyderabad",
        code: "HYD",
        airport: "Rajiv Gandhi International Airport",
        country: "India",
        category: "domestic"
    },
    {
        city: "Chennai",
        code: "MAA",
        airport: "Chennai International Airport",
        country: "India",
        category: "domestic"
    },
    {
        city: "Kolkata",
        code: "CCU",
        airport: "Netaji Subhas Chandra Bose International Airport",
        country: "India",
        category: "domestic"
    },
    {
        city: "Jaipur",
        code: "JAI",
        airport: "Jaipur International Airport",
        country: "India",
        category: "domestic"
    },
    {
        city: "Ahmedabad",
        code: "AMD",
        airport: "Sardar Vallabhbhai Patel International Airport",
        country: "India",
        category: "domestic"
    },
    {
        city: "Goa",
        code: "GOI",
        airport: "Goa International Airport (Dabolim)",
        country: "India",
        category: "domestic"
    },
    {
        city: "Pune",
        code: "PNQ",
        airport: "Pune International Airport",
        country: "India",
        category: "domestic"
    },
    {
        city: "Kochi",
        code: "COK",
        airport: "Cochin International Airport",
        country: "India",
        category: "domestic"
    },
    {
        city: "Lucknow",
        code: "LKO",
        airport: "Chaudhary Charan Singh International Airport",
        country: "India",
        category: "domestic"
    },

    // Popular International Airports
    {
        city: "Dubai",
        code: "DXB",
        airport: "Dubai International Airport",
        country: "UAE",
        category: "international"
    },
    {
        city: "Singapore",
        code: "SIN",
        airport: "Singapore Changi Airport",
        country: "Singapore",
        category: "international"
    },
    {
        city: "London",
        code: "LHR",
        airport: "Heathrow Airport",
        country: "United Kingdom",
        category: "international"
    },
    {
        city: "New York",
        code: "JFK",
        airport: "John F. Kennedy International Airport",
        country: "USA",
        category: "international"
    },
    {
        city: "Bangkok",
        code: "BKK",
        airport: "Suvarnabhumi Airport",
        country: "Thailand",
        category: "international"
    }
];

// Maintain backward compatibility for global variable references
window.airports = window.NandiAirports.filter(a => a.category === "domestic");
window.internationalAirports = window.NandiAirports.filter(a => a.category === "international");