#include <map>
#include <string>
#include <vector>
#include <memory>
#include <stdexcept>
#include <pybind11/pybind11.h>
#include <pybind11/stl.h>

namespace py = pybind11;

// forward declarations
struct Order;
struct Fill;

// order book side (bids or asks)
enum class Side {
    BUY,
    SELL
};

// represents a single order
struct Order {
    std::string order_id;
    Side side;
    double price;
    double size;
    int64_t timestamp;

    Order(std::string id, Side s, double p, double sz, int64_t ts)
        : order_id(std::move(id)), side(s), price(p), size(sz), timestamp(ts) {}
};

// represents a fill event
struct Fill {
    std::string taker_order_id;
    std::string maker_order_id;
    double price;
    double size;
    int64_t timestamp;

    Fill(std::string taker, std::string maker, double p, double sz, int64_t ts)
        : taker_order_id(std::move(taker)), maker_order_id(std::move(maker)),
          price(p), size(sz), timestamp(ts) {}
};

// price level in the order book
struct PriceLevel {
    std::vector<std::shared_ptr<Order>> orders;
};

// common type for ask book (ascending)
using AskBook = std::map<double, PriceLevel, std::less<double>>;
// common type for bid book (descending)
using BidBook = std::map<double, PriceLevel, std::greater<double>>;

class MatchEngine {
private:
    // price -> orders at that price
    BidBook bids;
    AskBook asks;
    // order_id -> (side, price)
    std::map<std::string, std::pair<Side, double>> order_map;

    std::vector<Fill> match_buy(std::shared_ptr<Order>& order) {
        if (!order) {
            throw std::invalid_argument("Order cannot be null");
        }
        if (order->size <= 0) {
            throw std::invalid_argument("Order size must be positive");
        }
        std::vector<Fill> fills;
        
        auto ask_it = asks.begin();
        while (ask_it != asks.end() && order->size > 0) {
            if (ask_it->first > order->price) break;
            
            auto& level = ask_it->second;
            auto order_it = level.orders.begin();
            
            while (order_it != level.orders.end() && order->size > 0) {
                auto maker = *order_it;
                if (!maker || maker->size <= 0) {
                    order_it = level.orders.erase(order_it);
                    continue;
                }
                
                double match_size = std::min(order->size, maker->size);
                fills.emplace_back(
                    order->order_id,
                    maker->order_id,
                    ask_it->first,
                    match_size,
                    order->timestamp
                );
                
                order->size -= match_size;
                maker->size -= match_size;
                
                if (maker->size <= 0) {
                    order_map.erase(maker->order_id);
                    order_it = level.orders.erase(order_it);
                } else {
                    ++order_it;
                }
            }
            
            if (level.orders.empty()) {
                ask_it = asks.erase(ask_it);
            } else {
                ++ask_it;
            }
        }
        
        return fills;
    }
    
    std::vector<Fill> match_sell(std::shared_ptr<Order>& order) {
        if (!order) {
            throw std::invalid_argument("Order cannot be null");
        }
        if (order->size <= 0) {
            throw std::invalid_argument("Order size must be positive");
        }
        std::vector<Fill> fills;
        
        auto bid_it = bids.begin();
        while (bid_it != bids.end() && order->size > 0) {
            if (bid_it->first < order->price) break;
            
            auto& level = bid_it->second;
            auto order_it = level.orders.begin();
            
            while (order_it != level.orders.end() && order->size > 0) {
                auto maker = *order_it;
                if (!maker || maker->size <= 0) {
                    order_it = level.orders.erase(order_it);
                    continue;
                }
                
                double match_size = std::min(order->size, maker->size);
                fills.emplace_back(
                    order->order_id,
                    maker->order_id,
                    bid_it->first,
                    match_size,
                    order->timestamp
                );
                
                order->size -= match_size;
                maker->size -= match_size;
                
                if (maker->size <= 0) {
                    order_map.erase(maker->order_id);
                    order_it = level.orders.erase(order_it);
                } else {
                    ++order_it;
                }
            }
            
            if (level.orders.empty()) {
                bid_it = bids.erase(bid_it);
            } else {
                ++bid_it;
            }
        }
        
        return fills;
    }
    
    void add_to_book(const std::shared_ptr<Order>& order) {
        if (!order) {
            throw std::invalid_argument("Order cannot be null");
        }
        if (order->size <= 0) {
            throw std::invalid_argument("Order size must be positive");
        }
        if (order->price <= 0) {
            throw std::invalid_argument("Order price must be positive");
        }
        if (order->order_id.empty()) {
            throw std::invalid_argument("Order ID cannot be empty");
        }
        
        if (order->side == Side::BUY) {
            bids[order->price].orders.push_back(order);
        } else {
            asks[order->price].orders.push_back(order);
        }
        order_map[order->order_id] = {order->side, order->price};
    }

public:
    std::vector<Fill> insert(const std::string& order_id, Side side, 
                            double price, double size, int64_t timestamp) {
        if (order_id.empty()) {
            throw std::invalid_argument("Order ID cannot be empty");
        }
        if (price <= 0) {
            throw std::invalid_argument("Price must be positive");
        }
        if (size <= 0) {
            throw std::invalid_argument("Size must be positive");
        }
        if (timestamp < 0) {
            throw std::invalid_argument("Timestamp must be non-negative");
        }
        
        auto order = std::make_shared<Order>(order_id, side, price, size, timestamp);
        std::vector<Fill> fills;
        
        try {
            if (side == Side::BUY) {
                fills = match_buy(order);
            } else {
                fills = match_sell(order);
            }
            
            if (order->size > 0) {
                add_to_book(order);
            }
            
            return fills;
        } catch (const std::exception& e) {
            throw std::runtime_error(std::string("Error in insert: ") + e.what());
        }
    }
    
    bool cancel(const std::string& order_id) {
        if (order_id.empty()) {
            throw std::invalid_argument("Order ID cannot be empty");
        }
        
        auto it = order_map.find(order_id);
        if (it == order_map.end()) {
            return false;
        }
        
        auto [side, price] = it->second;
        order_map.erase(it);
        
        if (side == Side::BUY) {
            auto bid_it = bids.find(price);
            if (bid_it != bids.end()) {
                auto& orders = bid_it->second.orders;
                orders.erase(
                    std::remove_if(orders.begin(), orders.end(),
                        [&order_id](const std::shared_ptr<Order>& order) {
                            return order && order->order_id == order_id;
                        }
                    ),
                    orders.end()
                );
                if (orders.empty()) {
                    bids.erase(bid_it);
                }
            }
        } else {
            auto ask_it = asks.find(price);
            if (ask_it != asks.end()) {
                auto& orders = ask_it->second.orders;
                orders.erase(
                    std::remove_if(orders.begin(), orders.end(),
                        [&order_id](const std::shared_ptr<Order>& order) {
                            return order && order->order_id == order_id;
                        }
                    ),
                    orders.end()
                );
                if (orders.empty()) {
                    asks.erase(ask_it);
                }
            }
        }
        
        return true;
    }
};

PYBIND11_MODULE(match_engine, m) {
    py::enum_<Side>(m, "Side")
        .value("BUY", Side::BUY)
        .value("SELL", Side::SELL)
        .export_values();
    
    py::class_<Fill>(m, "Fill")
        .def_readonly("taker_order_id", &Fill::taker_order_id)
        .def_readonly("maker_order_id", &Fill::maker_order_id)
        .def_readonly("price", &Fill::price)
        .def_readonly("size", &Fill::size)
        .def_readonly("timestamp", &Fill::timestamp);
    
    py::class_<MatchEngine>(m, "MatchEngine")
        .def(py::init<>())
        .def("insert", &MatchEngine::insert)
        .def("cancel", &MatchEngine::cancel);
} 