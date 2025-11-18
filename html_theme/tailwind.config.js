module.exports = {
  content: ["./layouts/*.html"],
  theme: {
    container: {
      center: true,
    },
    fontSize: {
      xs: ["12px", "16.2px"],
      sm: ["14px", "18.9px"],
      lg: ["16px", "21.6px"],
      xl: ["24px", "32.4px"],
    },
    screens: {
      sm: "600px",
      md: "728px",
      lg: "984px",
      xl: "1082px",
      // "2xl": "1496px",
    },
    extend: {
      defaultBlue: "#3F37C9",
    },
  },

  plugins: [require("flowbite/plugin")],
};
