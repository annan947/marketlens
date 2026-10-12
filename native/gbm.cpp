// Exact-discretization GBM using NumPy-generated shocks for engine parity.
#include <pybind11/pybind11.h>
#include <pybind11/numpy.h>
#include <cmath>
#include <stdexcept>
#include <vector>

namespace py = pybind11;

py::array_t<double> paths_from_shocks(double spot, double drift, double volatility,
                                     double years,
                                     py::array_t<double, py::array::c_style> shocks) {
    if (!std::isfinite(spot) || spot <= 0 || !std::isfinite(drift) ||
        !std::isfinite(volatility) || volatility < 0 || !std::isfinite(years) || years <= 0)
        throw std::invalid_argument("GBM parameters must be finite and in their valid domains");
    if (shocks.ndim() != 2 || shocks.shape(0) < 1 || shocks.shape(1) < 1)
        throw std::invalid_argument("shocks must be a nonempty two-dimensional float64 matrix");
    const auto steps = shocks.shape(0), paths = shocks.shape(1);
    if (steps >= 5000000 || paths > 5000000 / (steps + 1))
        throw std::invalid_argument("simulation must contain at most 5000000 path values");
    // Own a snapshot before releasing the GIL; callers cannot mutate our input buffer.
    std::vector<double> input(shocks.data(), shocks.data() + steps * paths);
    py::array_t<double> result({steps + 1, paths});
    double* output = result.mutable_data();
    {
        py::gil_scoped_release release;
        const double dt = years / static_cast<double>(steps);
        const double diffusion = volatility * std::sqrt(dt);
        const double trend = (drift - 0.5 * volatility * volatility) * dt;
        const double log_spot = std::log(spot);
        std::vector<double> cumulative(static_cast<size_t>(paths), 0.0);
        for (py::ssize_t j = 0; j < paths; ++j) output[j] = spot;
        for (py::ssize_t i = 0; i < steps; ++i) {
            for (py::ssize_t j = 0; j < paths; ++j) {
                const double shock = input[i * paths + j];
                if (!std::isfinite(shock)) throw std::invalid_argument("shocks must be finite");
                cumulative[j] += shock * diffusion + trend;
                const double price = std::exp(log_spot + cumulative[j]);
                if (!std::isfinite(price) || price <= 0)
                    throw std::invalid_argument("simulation parameters exceed numerical range");
                output[(i + 1) * paths + j] = price;
            }
        }
    }
    return result;
}

PYBIND11_MODULE(_gbm_native, module) {
    module.doc() = "MarketLens optional GBM path kernel; randomness is supplied by NumPy";
    module.def("paths_from_shocks", &paths_from_shocks,
        py::arg("spot"), py::arg("drift"), py::arg("volatility"), py::arg("years"),
        py::arg("shocks").noconvert());
}
